"""python -m pipeline.main corpus/ output/ [--docs SLUG,...] [--limit N] [--concurrency 4] [--thinking on|off] [--prompt FILE]

Stages: 1 preprocess -> 2 grounding -> 3 LLM extraction -> 4 parse + expand -> 5 guard + merge -> 6 write + validate.
One paper failing never stops the run; every paper in corpus/index.csv still gets a source_documents entry."""
from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from .expand import expand_claims
from .extract import Client, ConfigError, DEFAULT_PROMPT, LLMError, ROOT, config_from_env, extract_paper, glean, load_prompt
from .parse import check_sentences, parse_text
from . import doi as doimod
from .features import OFF, Features, add_provenance
from . import study as studymod
from .guard import guard_paper, merge
from .ontology_stage import FIELD_SETS as ONTOLOGY_FIELDS, MODES as ONTOLOGY_MODES, regrounded, stage_from_args
from .preprocess.assemble import Options, process_paper as process_paper_ours
from .preprocess.legend import load_taxon_table
from .preprocess.tokens import get_counter
from .write import summary, validate_outputs, validate_yaml_file, write_outputs, write_yaml

log = logging.getLogger("pipeline")


def get_preprocessor(name: str):
    if name == "sentence-chunks":
        from .preprocess.chunks import process_paper_sentence_chunks
        return process_paper_sentence_chunks
    if name == "paragraph-chunks":
        from .preprocess.team_adapter import process_paper_team_chunks
        return process_paper_team_chunks
    if name in ("paragraph", "team"):
        from .preprocess.team_adapter import process_paper_team
        return process_paper_team
    if name not in ("sentence", "ours"):
        raise ConfigError(f"--preprocess must be 'sentence', 'sentence-chunks', 'paragraph' or 'paragraph-chunks', not {name!r}")
    return process_paper_ours


process_paper = process_paper_ours

UNDER_EXTRACTION = 0.15         # claims per kept sentence below which --retry-underextraction retries: 9 of 308 papers in
                                # the full run of 2026-11-13 (5th percentile 0.19; 2F76GVEE 0.05 = 8 edges where the gold has 76)


def underextracted(n_claims: int, n_sentences: int) -> bool:
    return n_sentences >= 20 and n_claims / n_sentences < UNDER_EXTRACTION


def read_index(corpus: Path) -> List[Dict[str, str]]:
    with open(corpus / "index.csv", encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("slug")]


def process_one(row: Dict[str, str], corpus: Path, client: Client, system: str, count, table, max_input_tokens: int,
                pre_fn=None, opts: Optional[Options] = None, retry_client: Optional[Client] = None, ontology=None,
                features: Features = OFF, stamp: Optional[tuple] = None, continue_truncated: bool = False,
                study_client: Optional[Client] = None, glean_mode: str = "off") -> dict:
    slug = row["slug"]
    out = {"doc": slug, "error": None, "prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0, "chunks": 0,
           "nodes": {}, "edges": [], "stats": {}}
    t0 = time.time()
    try:
        raw = (corpus / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
        pre = (pre_fn or process_paper)(slug, raw, row, count, opts or Options(), table)       # stage 1 (+2: legend IDs)
        valid = [s["n"] for s in pre.sidecar["sentences"]]
        if not valid:
            raise RuntimeError("preprocessing kept no sentences")
        ex = extract_paper(client, system, pre.txt, valid, max_input_tokens, slug, pre.sidecar.get("chunk_texts"),
                           continue_truncated)                                                                    # stage 3
        if retry_client is not None and underextracted(len(ex.claims), len(valid)):
            ex2 = extract_paper(retry_client, system, pre.txt, valid, max_input_tokens, slug, pre.sidecar.get("chunk_texts"),
                                continue_truncated)
            out["retry"] = {"claims_first": len(ex.claims), "claims_retry": len(ex2.claims)}
            log.info("%s: under-extraction retry: %d -> %d claims", slug, len(ex.claims), len(ex2.claims))
            ex2.prompt_tokens += ex.prompt_tokens; ex2.completion_tokens += ex.completion_tokens; ex2.seconds += ex.seconds
            if len(ex2.claims) > len(ex.claims):
                ex = ex2
            else:
                ex.prompt_tokens, ex.completion_tokens, ex.seconds = ex2.prompt_tokens, ex2.completion_tokens, ex2.seconds
        if glean_mode != "off":                                                              # --glean
            glean(client, system, pre.txt, pre.sidecar["sentences"], ex, valid, glean_mode, slug)
        out.update(prompt_tokens=ex.prompt_tokens, completion_tokens=ex.completion_tokens, seconds=ex.seconds, chunks=ex.chunks)
        exp = expand_claims(slug, ex.claims, pre.sidecar, features)                           # stage 4
        nodes, edges, stats = guard_paper(slug, exp.nodes, exp.edges, features)               # stage 5 (per paper)
        if ontology is not None:                                                              # stage 5b (--ontology)
            nodes, edges, ostats, otok = regrounded(nodes, edges, slug, ontology, guard_paper)
            stats.update(ostats)
            out["prompt_tokens"] += otok["prompt_tokens"]
            out["completion_tokens"] += otok["completion_tokens"]
        if study_client is not None:                                                         # --study
            facts, stok = studymod.study_facts(study_client, row.get("title", ""), pre.sidecar.get("context", ""), slug)
            out["prompt_tokens"] += stok["prompt_tokens"]
            out["completion_tokens"] += stok["completion_tokens"]
            out["study"] = facts
            stats["study: evidence_types from the study design"] += studymod.apply_design(edges, facts.get("study_design"))
        if features.provenance and stamp:                                                    # --provenance (last: final IDs)
            add_provenance(nodes, edges, *stamp)
        out.update(nodes=nodes, edges=edges, stats=dict(stats))
        out["counts"] = {"sentences": len(valid), "claims": len(ex.claims), "bad_lines": ex.n_bad, "repaired": ex.n_repaired,
                         "dropped_lines": ex.n_dropped_lines, "dropped_sentence_refs": ex.n_dropped_sentences,
                         "edges_expanded": len(exp.edges), "edges_kept": len(edges),
                         "truncated_calls": ex.n_truncated, "continuation_calls": ex.n_continued,
                         "glean_calls": ex.n_glean_calls, "gleaned_claims": ex.n_gleaned}
        out["modes"] = sorted(set(ex.modes))
    except Exception as e:  # noqa: BLE001 - isolate every paper
        out["error"] = f"{type(e).__name__}: {e}"
        log.warning("%s failed: %s", slug, out["error"])
        log.debug("%s", traceback.format_exc())
    out["wall"] = time.time() - t0
    return out


def run(corpus: Path, out_dir: Path, docs: Optional[List[str]] = None, limit: Optional[int] = None, concurrency: int = 4,
        thinking: bool = False, prompt: str = DEFAULT_PROMPT, use_cache: bool = True, max_input_tokens: int = 12000,
        max_tokens: int = 3000, preprocess: str = "paragraph-chunks", refresh_cache: bool = False, cite_filter: str = "strict",
        taxon_groups: bool = False, retry_underextraction: bool = False, ontology: str = "off", ontology_fields: str = "all",
        features: Features = OFF, continue_truncated: bool = False, study: bool = False, glean_mode: str = "off") -> int:
    t0 = time.time()
    opts = Options(cite_filter=cite_filter, taxon_groups=taxon_groups)
    pre_fn = get_preprocessor(preprocess)
    cfg = config_from_env(thinking, use_cache, max_tokens)
    cfg.refresh_cache = refresh_cache                 # raises ConfigError if a variable is missing
    pname, system = load_prompt(prompt)
    index = read_index(corpus)
    todo = [r for r in index if not docs or r["slug"] in docs]
    if docs:
        missing = sorted(set(docs) - {r["slug"] for r in index})
        if missing:
            raise ConfigError(f"--docs not in index.csv: {', '.join(missing)}")
    if limit:
        todo = todo[:limit]
    count, tok_name = get_counter(allow_download=False)
    table = load_taxon_table()
    client = Client(cfg, retry_log=out_dir / "retries.csv")
    client.init_retry_log()
    retry_client = None
    if retry_underextraction:
        rcfg = copy.copy(cfg)
        rcfg.cache_salt = "underextraction-retry-1"        # its own cache entry: cached re-runs reproduce the retry exactly
        retry_client = Client(rcfg, retry_log=out_dir / "retries.csv")
    onto = stage_from_args(ontology, ontology_fields, cfg, Client)
    study_client = studymod.make_client(cfg, Client) if study else None
    import datetime as _dt
    stamp = (cfg.model, _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    log.info("prompt=%s thinking=%s tokenizer=%s papers=%d concurrency=%d", pname, "on" if thinking else "off", tok_name, len(todo), concurrency)
    outcomes: List[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futs = [pool.submit(process_one, r, corpus, client, system, count, table, max_input_tokens, pre_fn, opts, retry_client, onto,
                            features, stamp, continue_truncated, study_client, glean_mode)
                for r in todo]
        for f in futs:
            outcomes.append(f.result())
            done += 1
            if done % 10 == 0 or done == len(futs):
                log.info("%d/%d papers done (%d failed)", done, len(futs), sum(1 for o in outcomes if o["error"]))
    if onto is not None:
        onto.close()
        log.info("%s", onto.summary())
    per_doc = {o["doc"]: (o["nodes"], o["edges"]) for o in outcomes}
    dois = doimod.resolve_all(index, corpus)                               # DOI fallback for rows with an empty DOI cell
    graph = merge(index, per_doc, dois={s: d.doi for s, d in dois.items()},
                  study={o["doc"]: o["study"] for o in outcomes if o.get("study")})   # raises if there is not a single edge
    doimod.write_report(out_dir / "doi_report.csv", index, dois)
    yp, jp = write_outputs(graph, out_dir)
    errors, validators = validate_outputs(graph, yp, jp)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "tokens.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc", "prompt_tokens", "completion_tokens", "seconds", "chunks", "thinking"])
        for o in outcomes:
            w.writerow([o["doc"], o["prompt_tokens"], o["completion_tokens"], f"{o['seconds']:.2f}", o["chunks"], "on" if thinking else "off"])
    with open(out_dir / "run_log.json", "w", encoding="utf-8") as f:
        json.dump({"prompt": pname, "preprocess": preprocess, "cite_filter": cite_filter, "taxon_groups": taxon_groups,
                   "retry_underextraction": retry_underextraction, "ontology": ontology, "ontology_fields": ontology_fields,
                   "features": sorted(k for k, v in vars(features).items() if v),
                   "continue_truncated": continue_truncated, "study": study, "glean": glean_mode, "thinking": "on" if thinking else "off", "model": cfg.model, "tokenizer": tok_name,
                   "papers": [{k: v for k, v in o.items() if k not in ("nodes", "edges")} for o in outcomes]}, f, indent=1)
    print(summary(graph, outcomes, time.time() - t0, validators, doimod.counts(dois)))
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} problems):", file=sys.stderr)
        for e in errors[:20]:
            print("  " + e, file=sys.stderr)
        return 1
    return 0


def run_smoke(slug: str, corpus: Path, out_dir: Path, prompt: str = DEFAULT_PROMPT, max_tokens: int = 3000) -> int:
    """One real call on one paper, with the cache bypassed, to measure the endpoint before a full run."""
    from urllib.parse import urlparse
    import os

    names = ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY")
    print("environment: " + ", ".join(f"{n} {'set' if os.environ.get(n, '').strip() else 'MISSING'}" for n in names))
    cfg = config_from_env(thinking=False, use_cache=False, max_tokens=max_tokens)      # raises ConfigError naming what is missing
    pname, system = load_prompt(prompt)
    index = read_index(corpus)
    row = next((r for r in index if r["slug"] == slug), None)
    if row is None:
        raise ConfigError(f"--smoke: {slug} is not in index.csv")
    print(f"endpoint host: {urlparse(cfg.url).hostname}   model: {cfg.model}   prompt: {pname}   thinking: off   cache: bypassed")
    count, _ = get_counter(allow_download=False)
    raw = (corpus / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    pre = process_paper(slug, raw, row, count, Options(), load_taxon_table())
    valid = [s["n"] for s in pre.sidecar["sentences"]]
    print(f"input: {len(pre.txt):,} characters, {len(valid)} numbered sentences (estimated {int(len(pre.txt) / 3.5):,} tokens)")
    client = Client(cfg)
    try:
        r = client.complete(system, pre.txt, slug)
    except LLMError as e:
        print(f"CALL FAILED: {e}", file=sys.stderr)
        return 1
    mode = {"off (kwargs)": "accepted (chat_template_kwargs enable_thinking=false)",
            "off (/no_think)": "REJECTED, fell back to /no_think in the user message"}.get(r.thinking_mode, r.thinking_mode)
    tps = r.completion_tokens / r.seconds if r.seconds else float("nan")
    claims, bad = parse_text(r.text)
    n_f, n_n = sum(1 for c in claims if c.kind == "F"), sum(1 for c in claims if c.kind == "N")
    kept, dropped = check_sentences(claims, valid)
    print(f"thinking-off parameter: {mode}")
    print(f"<think> block returned: {'YES (stripped before parsing)' if r.think_returned else 'no'}")
    print(f"tokens: prompt {r.prompt_tokens:,}, completion {r.completion_tokens:,}")
    print(f"seconds: {r.seconds:.1f}   completion tokens per second: {tps:.1f}")
    print(f"lines parsed: {n_f} F + {n_n} N; unparseable: {len(bad)}; claims citing only unknown sentences: {dropped}")
    for b in bad[:5]:
        print(f"  unparseable: {b[:140]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    rp = out_dir / f"smoke_{slug}.txt"
    rp.write_text(r.raw or r.text, encoding="utf-8")
    print(f"raw response saved: {rp}")
    exp = expand_claims(slug, kept, pre.sidecar)
    nodes, edges, stats = guard_paper(slug, exp.nodes, exp.edges)
    if not edges:
        print("no edges survived expansion and the guard: nothing to write or validate")
        return 1
    graph = merge([row], {slug: (nodes, edges)})
    gp = write_yaml(graph, out_dir / f"smoke_{slug}.yaml")
    errors, ran = validate_yaml_file(graph, gp)
    print(f"graph saved: {gp}  ({len(edges)} edges, {len(nodes)} nodes, {sum(1 for e in edges if e.get('negated'))} null results; "
          f"guard: {dict(stats) or 'no repairs needed'})")
    print("validation: " + ran + (" -> OK, no errors" if not errors else f" -> {len(errors)} PROBLEMS"))
    for e in errors[:10]:
        print("  " + e, file=sys.stderr)
    return 1 if errors else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.main", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", nargs="?")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--smoke", metavar="SLUG", help="one real call on this paper (cache bypassed), reported and saved under dev/out/")
    ap.add_argument("--smoke-dir", default=str(ROOT / "dev" / "out"), help=argparse.SUPPRESS)
    ap.add_argument("--docs", help="comma-separated slugs (default: all)")
    ap.add_argument("--limit", type=int, help="only the first N papers")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--thinking", choices=("on", "off"), default="off")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="file in pipeline/prompt/ (default system.txt)")
    ap.add_argument("--preprocess", choices=("sentence", "sentence-chunks", "paragraph", "paragraph-chunks"), default="paragraph-chunks", help="stage 1: paragraph-level scoring and selection with one call per paragraph chunk (team_paper.py; default), the same with the whole paper in one call (paragraph), or sentence-level filtering (sentence; sentence-chunks = the same sentences, one call per ~2,500-token chunk)")
    ap.add_argument("--cite-filter", choices=("strict", "relaxed"), default="strict", help="relaxed: in discussion/conclusions also keep cited sentences that refer back to the authors' own results")
    ap.add_argument("--taxon-groups", action="store_true", help="group words (rodents, conifers, grasses, ...) get a SPECIES legend entry with the group's NCBITaxon ID")
    ap.add_argument("--retry-underextraction", action="store_true", help="retry a paper once (own cache entry) when claims per sentence fall below UNDER_EXTRACTION")
    ap.add_argument("--ontology", choices=ONTOLOGY_MODES, default="off", help="stage 5b, ontology/ground_terms.py: lookup = IDs for unique exact matches in the committed indexes (ELMO, ENVO, GO, PATO, ChEBI, PO, UBERON; no LLM); select = also let the model pick among candidates by number (one short call per paper)")
    ap.add_argument("--ontology-fields", choices=ONTOLOGY_FIELDS, default="all", help="entities: ground entity_term and life_stage_term only, keep measured_attribute as free text")
    ap.add_argument("--glean", choices=("off", "auto", "always"), default="off", help="one extra call per paper on result/discussion sentences no claim cites (auto: only those with a significance token or a result word, and only if there are at least 3)")
    ap.add_argument("--study", action="store_true", help="one short call per paper on the CONTEXT block: study design, country, region and years for source_documents; evidence_types from the design")
    ap.add_argument("--continue-truncated", action="store_true", help="when a reply is cut off at --max-tokens, send the sentences after the last one it cited (at most twice per chunk)")
    ap.add_argument("--fit-attributes", action="store_true", help="life-stage and direction words leave measured_attribute (life_stage, life_stage_term, qualifier)")
    ap.add_argument("--double-negative", action="store_true", help="'prevents' with a 'decreased' object becomes 'causes'")
    ap.add_argument("--provenance", action="store_true", help="annotator, annotation_timestamp and variable_key on nodes and edges")
    ap.add_argument("--refresh-cache", action="store_true", help="call the model even when an answer is cached, and store the new answer")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--max-input-tokens", type=int, default=12000)
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        if a.smoke:
            return run_smoke(a.smoke, Path(a.corpus) if a.corpus else ROOT / "corpus", Path(a.smoke_dir), a.prompt, a.max_tokens)
        if not a.corpus or not a.output:
            ap.error("corpus and output directories are required (or use --smoke SLUG)")
        return run(Path(a.corpus), Path(a.output), [d.strip() for d in a.docs.split(",") if d.strip()] if a.docs else None, a.limit,
                   a.concurrency, a.thinking == "on", a.prompt, not a.no_cache, a.max_input_tokens, a.max_tokens, a.preprocess, a.refresh_cache,
                   a.cite_filter, a.taxon_groups, a.retry_underextraction, a.ontology, a.ontology_fields,
                   Features(a.fit_attributes, a.double_negative, a.provenance), a.continue_truncated, a.study, a.glean)
    except (ConfigError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2 if isinstance(e, ConfigError) else 1


if __name__ == "__main__":
    sys.exit(main())
