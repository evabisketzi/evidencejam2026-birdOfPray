#!/usr/bin/env python3
"""
preprocess_corpus.py
====================

Corpus-level preprocessing for Evidence Jam 2026, Lane 1.

For every article in corpus/ (and every row of corpus/index.csv) this:

  1. builds the CAMO SourceDocument entry from index.csv
     (document_id = normalised DOI, doi, title, authors[list], year[int], journal);
  2. cleans the markdown, selects paragraphs and packs LLM chunks + a study card
     (all logic lives in preprocess_paper.py);
  3. writes one JSON per article, ready for the LLM extraction stage;
  4. writes source_documents.json (ALL articles, including ones that fail),
     a per-article report (CSV + JSON) and the settings used.

Character offsets in the outputs are relative to the article text exactly as
``Path(md).read_text(encoding="utf-8")`` returns it (the same call as the
starter code), so they can go straight into CAMO TextSpan.start_char/end_char.

Pure standard library (Python 3.9+). No network, no LLM calls.

Usage
-----
    python preprocess_corpus.py corpus/ output/preprocessed
    python preprocess_corpus.py corpus/ output/preprocessed --limit 20 --max-chunk-tokens 3000
    python preprocess_corpus.py corpus/ output/preprocessed --ablation 15     # corpus-wide step savings
    python preprocess_corpus.py corpus/ output/preprocessed --validate-schema schema/causalmosaic.yaml

Outputs (in OUT_DIR)
--------------------
    articles/<slug>.json      paragraphs (+offsets), chunks, study card, dropped blocks, health
    source_documents.json     list of CAMO SourceDocument dicts, one per article
    doc_ids.json              {slug: document_id}
    corpus_report.csv/.json   per-article tokens, chunks, warnings
    preprocess_config.json    every setting used (for reproducibility)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # find preprocess_paper.py from any cwd
from preprocess_paper import (Config, PackConfig, make_token_counter, pack, preprocess,  # noqa: E402
                              ablation_rows, print_ablation)

SCHEMA_VERSION = "0.10.0"


# =============================================================================
# index.csv -> CAMO SourceDocument
# =============================================================================
def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (k or "").strip().lower()).strip("_")


_COLUMN_ALIASES = {
    "slug": ("slug", "id", "key", "file", "filename"),
    "doi": ("doi", "doi_url"),
    "title": ("title",),
    "authors": ("authors", "author", "creators"),
    "year": ("year", "publication_year", "pub_year", "date"),
    "journal": ("journal", "journal_title", "publication", "venue", "source", "container_title"),
    "word_count": ("word_count", "words", "wordcount", "n_words"),
}


def read_index(path: Path) -> tuple[dict[str, dict], list[str]]:
    """Read index.csv into {slug: {field: value}} with tolerant column names."""
    warnings: list[str] = []
    if not path.exists():
        return {}, [f"index file not found: {path}"]
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = {_norm_key(c): c for c in (reader.fieldnames or [])}
        mapping = {}
        for field, aliases in _COLUMN_ALIASES.items():
            for a in aliases:
                if a in cols:
                    mapping[field] = cols[a]
                    break
        if "slug" not in mapping:
            return {}, [f"index has no slug column (columns: {reader.fieldnames})"]
        missing = [f for f in ("doi", "title", "year") if f not in mapping]
        if missing:
            warnings.append(f"index columns not found: {missing} (columns: {reader.fieldnames})")
        rows: dict[str, dict] = {}
        for raw in reader:
            row = {f: (raw.get(c) or "").strip() for f, c in mapping.items()}
            slug = Path(row["slug"]).stem
            if not slug:
                continue
            if slug in rows:
                warnings.append(f"duplicate slug in index: {slug} (first row kept)")
                continue
            rows[slug] = row
    return rows, warnings


_DOI_PREFIX = re.compile(r"^\s*(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*|doi\s+)", re.I)
DOI_RX = re.compile(r"^10\.\d{4,9}/\S+$")


def normalize_doi(value: str) -> str:
    d = _DOI_PREFIX.sub("", value or "").strip().rstrip(".;,")
    return d


def split_authors(value: str) -> list[str]:
    """Split an author string without breaking 'Smith, J.' style names."""
    s = (value or "").strip()
    if not s:
        return []
    for sep in (";", "|", "\n"):
        if sep in s:
            return [a.strip() for a in s.split(sep) if a.strip()]
    if re.search(r"\s+(?:and|&)\s+", s) and s.count(",") <= 1:
        return [a.strip(" ,") for a in re.split(r"\s+(?:and|&)\s+", s) if a.strip(" ,")]
    # 'A. Smith, B. Jones, C. Lee' (initials first) -> safe to split on commas
    parts = [p.strip() for p in s.split(",")]
    if len(parts) > 1 and all(re.match(r"^(?:[A-Z]\.\s*)+[A-Z][\w'’\-]+", p) or
                              re.match(r"^[A-Z][a-z]+ [A-Z][\w'’\-]+$", p) for p in parts if p):
        return [p for p in parts if p]
    return [s]                                         # ambiguous: keep as one string


def parse_year(value: str) -> int | None:
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", value or "")
    return int(m.group(1)) if m else None


def slug_key(slug: str) -> str:
    """Lowercase, CURIE-safe version of a slug for node/edge ids (node:<slug_key>_n1)."""
    return re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_") or "doc"


def build_source_documents(index: dict[str, dict], md_slugs: list[str],
                           titles: dict[str, str] | None = None) -> tuple[list[dict], dict[str, str], list[str]]:
    """One SourceDocument per article (union of corpus files and index rows).
    Returns (documents, {slug: document_id}, warnings). document_ids are unique."""
    titles = titles or {}
    warnings: list[str] = []
    slugs = sorted(set(md_slugs) | set(index))
    for s in sorted(set(md_slugs) - set(index)):
        warnings.append(f"{s}: markdown file has no index.csv row (document_id = slug, no DOI)")
    for s in sorted(set(index) - set(md_slugs)):
        warnings.append(f"{s}: index.csv row has no markdown file (source document still emitted)")
    docs: list[dict] = []
    ids: dict[str, str] = {}
    used: set[str] = set()
    for s in slugs:
        row = index.get(s, {})
        doi = normalize_doi(row.get("doi", ""))
        if doi and not DOI_RX.match(doi):
            warnings.append(f"{s}: DOI does not look like a DOI: {doi!r} (kept as given)")
        doc_id = doi or s
        if doc_id in used:
            warnings.append(f"{s}: duplicate DOI {doi!r}; document_id made unique with slug")
            doc_id = f"{doi}#{s}"
        used.add(doc_id)
        ids[s] = doc_id
        d: dict = {"document_id": doc_id}
        if doi:
            d["doi"] = doi
        title = row.get("title") or titles.get(s, "")
        if title:
            d["title"] = title
        authors = split_authors(row.get("authors", ""))
        if authors:
            d["authors"] = authors
        year = parse_year(row.get("year", ""))
        if year:
            d["year"] = year
        if row.get("journal"):
            d["journal"] = row["journal"]
        docs.append(d)
    return docs, ids, warnings


def minimal_graph(source_documents: list[dict], graph_id: str = "evidencejam2026-lane1") -> dict:
    """A schema-valid CausalGraph with only source documents (used for checks and as the merge base)."""
    return {
        "graph_id": graph_id,
        "schema_version": SCHEMA_VERSION,
        "provenance": {"causal_mosaic_version": SCHEMA_VERSION,
                       "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "source_documents": source_documents,
        "nodes": [],
        "edges": [],
    }


# =============================================================================
# One article
# =============================================================================
def read_article(path: Path) -> str:
    """Same call as the starter code, so offsets agree with anyone re-reading the file."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def article_warnings(res, packed, ext_tokens: int) -> list[str]:
    secs = set(res.health["sections"])
    w = []
    if not res.paragraphs:
        w.append("no_paragraphs")
    if secs and secs <= {"title", "unknown", "front"}:
        w.append("no_sections_detected")
    elif "results" not in secs and "discussion" not in secs:
        w.append("no_results_or_discussion")
    if "abstract" not in secs:
        w.append("no_abstract")
    if ext_tokens < 300:
        w.append("few_extract_tokens")
    if ext_tokens > 10000:
        w.append("many_extract_tokens")
    if res.health["selection_dropped_with_statistic"] >= 2:
        w.append("selection_dropped_statistics")
    if res.health["starts_lowercase_share"] > 0:
        w.append("fragments_left")
    if not packed.chunks:
        w.append("no_chunks")
    return w


def process_article(path: Path, slug: str, doc_id: str, count, cfg: Config,
                    pcfg: PackConfig) -> tuple[dict, dict]:
    """Return (article_json, report_row). Bibliographic metadata lives only in
    source_documents.json; articles carry the document_id that points to it."""
    t0 = time.time()
    base = {"slug": slug, "slug_key": slug_key(slug), "document_id": doc_id}
    try:
        text = read_article(path)
        res = preprocess(text, tokenizer=count, source=str(path), config=cfg)
        packed = pack(res, pcfg, count)
        routes = res.tokens_by_route()
        ext = routes.get("extract", 0)
        warns = article_warnings(res, packed, ext)
        art = {
            **base,
            "error": None,
            "n_chars": len(text),
            "tokens_original": res.tokens_original,
            "tokens_by_route": routes,
            "health": res.health,
            "warnings": warns,
            "steps": [{"name": s.name, "category": s.category, "enabled": s.enabled,
                       "changes": s.changes, "saved": s.saved} for s in res.steps],
            "paragraphs": [p.to_dict() for p in res.paragraphs],
            "split_pieces": [q.to_dict() for q in packed.units.values() if q.parent],
            "study_card": packed.study_card.to_dict() if packed.study_card else None,
            "chunks": [c.to_dict() for c in packed.chunks],
            "dropped": res.dropped,
        }
        row = {
            "slug": slug, "document_id": doc_id, "error": "",
            "tokens_original": res.tokens_original, "extract_tokens": ext,
            "context_tokens": routes.get("context", 0), "paragraphs": len(res.paragraphs),
            "chunks": len(packed.chunks), "chunk_tokens": " ".join(str(c.n_tokens) for c in packed.chunks),
            "card_tokens": packed.study_card.n_tokens if packed.study_card else 0,
            "est_llm_input_tokens": packed.est_llm_input_tokens,
            "merged_continuations": res.health.get("merged_continuations", 0),
            "selection_dropped": res.health["selection_dropped"],
            "selection_dropped_with_statistic": res.health["selection_dropped_with_statistic"],
            "dropped_with_statistic": res.health["dropped_with_statistic"],
            "fragments_left": round(res.health["starts_lowercase_share"] * len(res.paragraphs)),
            "sections": " ".join(f"{k}:{v}" for k, v in sorted(res.health["sections"].items())),
            "warnings": " ".join(warns), "seconds": round(time.time() - t0, 3),
        }
    except Exception as e:  # never lose the whole run to one article
        msg = f"{type(e).__name__}: {e}"
        art = {**base, "error": msg, "paragraphs": [], "split_pieces": [], "study_card": None,
               "chunks": [], "dropped": [], "warnings": ["error"]}
        row = {"slug": slug, "document_id": doc_id, "error": msg, "warnings": "error",
               "seconds": round(time.time() - t0, 3)}
    return art, row


# =============================================================================
# Corpus
# =============================================================================
REPORT_COLUMNS = ["slug", "document_id", "error", "tokens_original", "extract_tokens", "context_tokens",
                  "paragraphs", "chunks", "chunk_tokens", "card_tokens", "est_llm_input_tokens",
                  "merged_continuations", "selection_dropped", "selection_dropped_with_statistic",
                  "dropped_with_statistic", "fragments_left", "sections", "warnings", "seconds"]


def corpus_ablation(paths: list[Path], n: int, seed: int, count, cfg: Config, pcfg: PackConfig) -> None:
    sample = sorted(random.Random(seed).sample(paths, min(n, len(paths))))
    totals: dict[str, dict] = {}
    order: list[str] = []
    for i, p in enumerate(sample, 1):
        print(f"  ablation {i}/{len(sample)}: {p.name}", file=sys.stderr)
        for r in ablation_rows(read_article(p), count, cfg, pcfg, str(p)):
            if r["config"] not in totals:
                totals[r["config"]] = {k: 0 for k in r if k != "config"}
                order.append(r["config"])
            for k, v in r.items():
                if k != "config":
                    totals[r["config"]][k] += v
    rows = [{"config": c, **totals[c]} for c in order]
    print_ablation(rows, f"CORPUS ABLATION over {len(sample)} articles (sums)")


def validate_source_documents(docs_path: Path, schema: Path) -> None:
    """Validate source_documents.json (a list) against the SourceDocument class (development check).
    Note: a CausalGraph with empty nodes/edges is valid as YAML but INVALID as JSON, so the
    documents are checked on their own here; the final graph must always contain nodes and edges."""
    exe = shutil.which("linkml-validate")
    if not exe:
        print(f"linkml-validate not on PATH; to check: linkml-validate -s {schema} -C SourceDocument {docs_path}")
        return
    r = subprocess.run([exe, "-s", str(schema), "-C", "SourceDocument", str(docs_path)],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(f"schema check of source documents: {'OK' if r.returncode == 0 else 'FAILED'}")
    if r.returncode:
        print(out[:2000])


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Preprocess the whole corpus for CAMO extraction.")
    ap.add_argument("corpus", help="folder with <slug>.md files and index.csv")
    ap.add_argument("out_dir", help="output folder, e.g. output/preprocessed")
    ap.add_argument("--index", help="path to index.csv (default: CORPUS/index.csv)")
    ap.add_argument("--limit", type=int, help="process only the first N articles (source documents still cover all)")
    ap.add_argument("--slugs", nargs="*", help="process only these slugs")
    ap.add_argument("--tokenizer", default="auto", help="auto | tiktoken | chars | hf:<model>")
    g = ap.add_argument_group("selection")
    g.add_argument("--min-score", type=float, default=Config.min_score)
    g.add_argument("--budget", type=int, default=None, help="max extract tokens per article")
    g.add_argument("--no-keep-null", action="store_true")
    g.add_argument("--no-keep-fragments", action="store_true")
    g = ap.add_argument_group("packing")
    g.add_argument("--max-chunk-tokens", type=int, default=PackConfig.max_chunk_tokens)
    g.add_argument("--max-paragraph-tokens", type=int, default=None)
    g.add_argument("--prompt-overhead", type=int, default=PackConfig.prompt_overhead_tokens)
    g.add_argument("--card-tokens", type=int, default=PackConfig.study_card_tokens)
    g.add_argument("--label", choices=["id_section", "id", "none"], default=PackConfig.label)
    g = ap.add_argument_group("checks")
    g.add_argument("--ablation", type=int, metavar="N", help="corpus ablation on N random articles, then exit")
    g.add_argument("--seed", type=int, default=13)
    g.add_argument("--validate-schema", metavar="SCHEMA", help="check source documents with linkml-validate")
    a = ap.parse_args(argv)

    corpus = Path(a.corpus)
    out = Path(a.out_dir)
    if not corpus.is_dir():
        ap.error(f"not a folder: {corpus}")
    count = make_token_counter(a.tokenizer)
    cfg = Config(min_score=a.min_score, keep_null_results=not a.no_keep_null,
                 keep_fragments=not a.no_keep_fragments, max_extract_tokens=a.budget)
    pcfg = PackConfig(max_chunk_tokens=a.max_chunk_tokens, max_paragraph_tokens=a.max_paragraph_tokens,
                      label=a.label, prompt_overhead_tokens=a.prompt_overhead, study_card_tokens=a.card_tokens)
    paths = sorted(corpus.glob("*.md"))

    if a.ablation:
        corpus_ablation(paths, a.ablation, a.seed, count, cfg, pcfg)
        return 0

    index, idx_warn = read_index(Path(a.index) if a.index else corpus / "index.csv")
    _, doc_ids, doc_warn = build_source_documents(index, [p.stem for p in paths])

    todo = paths
    if a.slugs:
        want = set(a.slugs)
        todo = [p for p in paths if p.stem in want]
    if a.limit:
        todo = todo[:a.limit]

    (out / "articles").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows: list[dict] = []
    titles: dict[str, str] = {}
    for i, p in enumerate(todo, 1):
        art, row = process_article(p, p.stem, doc_ids[p.stem], count, cfg, pcfg)
        if art.get("paragraphs") and art["paragraphs"][0]["section"] == "title":
            titles[p.stem] = art["paragraphs"][0]["text"][:300]
        (out / "articles" / f"{p.stem}.json").write_text(
            json.dumps(art, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        rows.append(row)
        flag = f"  ERROR {row['error']}" if row["error"] else (f"  [{row['warnings']}]" if row["warnings"] else "")
        print(f"[{i:>3}/{len(todo)}] {p.stem:<14} extract {row.get('extract_tokens', 0):>6}  "
              f"chunks {row.get('chunks', 0):>2}  LLM-in~{row.get('est_llm_input_tokens', 0):>6}{flag}")

    # final documents: index metadata, plus the markdown title for articles missing from index.csv
    # (document_ids do not depend on titles, so they match the ids written into the article files)
    docs, doc_ids, _ = build_source_documents(index, [p.stem for p in paths], titles)

    (out / "source_documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "doc_ids.json").write_text(json.dumps(doc_ids, indent=1), encoding="utf-8")
    with (out / "corpus_report.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    settings = {"created": datetime.now(timezone.utc).isoformat(), "tokenizer": a.tokenizer,
                "selection": cfg.__dict__ | {"always_keep_sections": list(cfg.always_keep_sections)},
                "packing": pcfg.__dict__, "n_articles_processed": len(todo),
                "n_source_documents": len(docs)}
    (out / "preprocess_config.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")

    ok = [r for r in rows if not r["error"]]
    summary = {
        "articles_processed": len(rows), "errors": len(rows) - len(ok), "source_documents": len(docs),
        "tokens_original": sum(r["tokens_original"] for r in ok),
        "extract_tokens": sum(r["extract_tokens"] for r in ok),
        "context_tokens": sum(r["context_tokens"] for r in ok),
        "chunks": sum(r["chunks"] for r in ok),
        "est_llm_input_tokens": sum(r["est_llm_input_tokens"] for r in ok),
        "merged_continuations": sum(r["merged_continuations"] for r in ok),
        "selection_dropped_with_statistic": sum(r["selection_dropped_with_statistic"] for r in ok),
        "warning_counts": dict(Counter(w for r in rows for w in r["warnings"].split() if w)),
        "seconds": round(time.time() - t0, 1),
        "index_warnings": idx_warn, "source_document_warnings": doc_warn,
    }
    (out / "corpus_report.json").write_text(json.dumps({"summary": summary, "articles": rows}, indent=1,
                                                       ensure_ascii=False), encoding="utf-8")

    print("\nSUMMARY")
    n = max(1, len(ok))
    saved = 1 - (summary["extract_tokens"] + summary["context_tokens"]) / max(1, summary["tokens_original"])
    print(f"  articles {len(rows)} (errors {summary['errors']}), source documents {len(docs)}, "
          f"{summary['seconds']} s")
    print(f"  tokens: original {summary['tokens_original']:,}  -> extract {summary['extract_tokens']:,} + "
          f"context {summary['context_tokens']:,}  ({100 * saved:.1f}% removed)")
    print(f"  chunks {summary['chunks']} (mean {summary['chunks'] / n:.1f}/article); "
          f"est. LLM input {summary['est_llm_input_tokens']:,} (mean {summary['est_llm_input_tokens'] // n:,}/article)")
    print(f"  merged split sentences {summary['merged_continuations']}; "
          f"selection dropped {summary['selection_dropped_with_statistic']} blocks containing statistics")
    if summary["warning_counts"]:
        print("  warnings: " + ", ".join(f"{k} {v}" for k, v in sorted(summary["warning_counts"].items())))
    for w in (idx_warn + doc_warn)[:15]:
        print(f"  ! {w}")
    if len(idx_warn + doc_warn) > 15:
        print(f"  ! ... {len(idx_warn + doc_warn) - 15} more in corpus_report.json")
    print(f"\nwrote {out}/articles/*.json, source_documents.json, doc_ids.json, corpus_report.csv/.json")

    if a.validate_schema:
        validate_source_documents(out / "source_documents.json", Path(a.validate_schema))
    return 0


if __name__ == "__main__":
    sys.exit(main())