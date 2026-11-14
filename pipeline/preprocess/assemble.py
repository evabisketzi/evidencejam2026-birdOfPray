"""Steps 1, 11, 12: run the whole pipeline for one paper and assemble its prompt text + sidecar."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import classify as C
from .clean import clean
from .context import build_context
from .filter import apply_filter
from .legend import Species, build_legend, format_legend, species_forms
from .sections import Para, SectionResult, detect_sections, split_paragraphs
from .sentences import naive_spans, split_spans
from .stats import compress_stats, detect_alpha
from .textmap import Mapped

log = logging.getLogger(__name__)


@dataclass
class Options:
    filter: bool = False
    context_tokens: int = 400
    max_legend: int = 25


@dataclass
class PaperResult:
    slug: str
    txt: str
    sidecar: Dict
    report: Dict


def _fallback_sections(cleaned: Mapped) -> SectionResult:
    paras = []
    for a, b in split_paragraphs(cleaned.s):
        p = Para(a, b, cleaned.s[a:b], "body", "res", True, "res")
        paras.append(p)
    return SectionResult(paras, [], ["sections_failed"])


def _sentence_spans(text: str, fallbacks: List[str]) -> List[tuple]:
    try:
        return split_spans(text)
    except Exception as e:  # noqa: BLE001
        log.warning("sentence splitter failed (%r); using naive splitter", e)
        if "sentences" not in fallbacks:
            fallbacks.append("sentences")
        try:
            return naive_spans(text)
        except Exception:  # noqa: BLE001
            return [(0, len(text))]


def process_paper(slug: str, raw: str, meta: Dict[str, str], count: Callable[[str], int], opts: Options,
                  taxon_table: Optional[Dict[str, int]] = None) -> PaperResult:
    fallbacks: List[str] = []
    try:
        return _process(slug, raw, meta, count, opts, taxon_table or {}, fallbacks)
    except Exception as e:  # noqa: BLE001 - never lose a paper
        log.exception("%s: pipeline failed (%r); emitting minimal fallback", slug, e)
        return _minimal(slug, raw, meta, count, fallbacks + ["paper_failed"])


def _minimal(slug, raw, meta, count, fallbacks) -> PaperResult:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", raw)).strip()
    spans = naive_spans(text) or [(0, len(text))]
    lines = [f"[{i}] (res) {text[a:b]}" for i, (a, b) in enumerate(spans, 1)]
    txt = f"TITLE: {meta.get('title', '')}\nSPECIES: \nCONTEXT: \nTEXT:\n" + "\n".join(lines) + "\n"
    n = count(raw)
    report = _report_row(slug, meta, {"raw": n, "clean": n, "cut": n, "cited": n, "stats": n, "filter": n, "final": count(txt)},
                         {}, [], fallbacks)
    side = {"slug": slug, **_meta(meta), "species": [], "context": "", "sentences": [], "dropped": [], "fallbacks": fallbacks}
    return PaperResult(slug, txt, side, report)


def _meta(meta: Dict[str, str]) -> Dict:
    return {k: meta.get(k, "") for k in ("doi", "title", "authors", "year", "journal", "word_count")}


def _report_row(slug, meta, tok, counts, sections, fallbacks) -> Dict:
    row = {"slug": slug, "doi": meta.get("doi", "")}
    for k in ("raw", "clean", "cut", "cited", "stats", "filter", "final"):
        row[f"tokens_{k}"] = tok.get(k, 0)
    row.update({
        "sentences_total": counts.get("total", 0),
        "sentences_kept": counts.get("kept", 0),
        "dropped_cited_background": counts.get("cited_background", 0),
        "dropped_filter": counts.get("filter", 0),
        "citations_stripped": counts.get("own_cue_stripped", 0),
        "sections_detected": ";".join(sections),
        "fallbacks": ";".join(fallbacks),
    })
    return row


def _process(slug, raw, meta, count, opts: Options, table, fallbacks: List[str]) -> PaperResult:
    tok: Dict[str, int] = {"raw": count(raw)}

    # ---- step 2: clean -------------------------------------------------------------------
    try:
        cr = clean(raw)
        cleaned = cr.cleaned
        fallbacks.extend(cr.fallbacks)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: clean failed (%r); using raw text", slug, e)
        cleaned = Mapped.from_raw(raw)
        fallbacks.append("clean")
    tok["clean"] = count(cleaned.s)

    # ---- steps 3-4: sections -------------------------------------------------------------
    try:
        sr = detect_sections(cleaned, meta.get("title", ""))
        fallbacks.extend(sr.fallbacks)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: section detection failed (%r); keeping everything as results", slug, e)
        sr = _fallback_sections(cleaned)
        fallbacks.append("sections")
    kept = [p for p in sr.paras if p.keep]

    # ---- step 5: sentences (with raw offsets) ----------------------------------------------
    sents: List[Dict] = []
    for p in kept:
        for a, b in _sentence_spans(p.text, fallbacks):
            text = p.text[a:b]
            if len(text.strip()) < 3:
                continue
            rs, re_ = cleaned.raw_span(p.start + a, p.start + b)
            sents.append({"section": p.tag, "start_char": rs, "end_char": re_, "raw": raw[rs:re_], "clean": text})
    tok["cut"] = count("\n".join(s["clean"] for s in sents))

    # ---- step 9: species legend (built from the whole text; pruned after assembly) ----------
    alpha = detect_alpha(cleaned.s)
    try:
        legend = build_legend(raw, cleaned.s, "\n".join(s["clean"] for s in sents), table, opts.max_legend)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: legend failed (%r)", slug, e)
        legend, _ = [], fallbacks.append("legend")
    forms = species_forms(legend)

    # ---- step 6: classify citations / own-study cues ------------------------------------------
    dropped: List[Dict] = []
    survivors: List[Dict] = []
    for s in sents:
        try:
            d = C.classify_sentence(s["clean"], forms)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: classify failed (%r); keeping sentence", slug, e)
            if "classify" not in fallbacks:
                fallbacks.append("classify")
            d = C.Decision(True, "kept", s["clean"], [], False)
        s["decision"], s["citations"], s["text1"] = d.reason, d.citations, d.text
        if not d.keep:
            dropped.append({"section": s["section"], "start_char": s["start_char"], "end_char": s["end_char"],
                            "clean": s["clean"], "reason": d.reason, "citations": d.citations})
            log.debug("%s: drop (%s): %.80s", slug, d.reason, s["clean"])
        else:
            survivors.append(s)
    tok["cited"] = count("\n".join(s["text1"] for s in survivors))

    # ---- step 7: statistics ---------------------------------------------------------------------
    for s in survivors:
        try:
            s["compressed"], s["stats"] = compress_stats(s["text1"], alpha)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: stats compression failed (%r)", slug, e)
            if "stats" not in fallbacks:
                fallbacks.append("stats")
            s["compressed"], s["stats"] = s["text1"], []
    tok["stats"] = count("\n".join(s["compressed"] for s in survivors))

    # ---- step 10: optional filter -------------------------------------------------------------------
    n_filter = 0
    if opts.filter:
        try:
            keep = apply_filter([s["compressed"] for s in survivors], forms)
            final = []
            for s, k in zip(survivors, keep):
                if k:
                    final.append(s)
                else:
                    n_filter += 1
                    dropped.append({"section": s["section"], "start_char": s["start_char"], "end_char": s["end_char"],
                                    "clean": s["clean"], "reason": "filtered", "citations": s["citations"]})
            survivors = final
        except Exception as e:  # noqa: BLE001
            log.warning("%s: filter failed (%r); not filtering", slug, e)
            fallbacks.append("filter")
    tok["filter"] = count("\n".join(s["compressed"] for s in survivors))

    # ---- step 8: background block ------------------------------------------------------------------------
    try:
        context = build_context(sr.intro_aims, [p.text for p in sr.methods], count, alpha, opts.context_tokens)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: context failed (%r)", slug, e)
        context, _ = "", fallbacks.append("context")

    # ---- step 11: assemble ---------------------------------------------------------------------------------
    for i, s in enumerate(survivors, 1):
        s["n"] = i
    shown = "\n".join(s["compressed"] for s in survivors) + "\n" + context
    pruned: List[Species] = []
    for sp in legend:
        forms_sp = [sp.name] + sp.variants
        if any(re.search(r"(?<![\w])" + re.escape(f) + r"(?![\w])", shown) for f in forms_sp):
            pruned.append(sp)
    legend = pruned
    lines = [f"[{s['n']}] ({s['section']}) {s['compressed']}" for s in survivors]
    txt = (f"TITLE: {meta.get('title', '')}\nSPECIES: {format_legend(legend)}\nCONTEXT: {context}\nTEXT:\n"
           + "\n".join(lines) + "\n")
    tok["final"] = count(txt)

    sidecar = {
        "slug": slug, **_meta(meta), "alpha": alpha,
        "species": [{"id": f"T{i}", "name": sp.name, "variants": sp.variants, "taxid": sp.taxid,
                     "ncbitaxon": f"NCBITaxon:{sp.taxid}" if sp.taxid else None} for i, sp in enumerate(legend, 1)],
        "context": context,
        "sentences": [{"n": s["n"], "section": s["section"], "start_char": s["start_char"], "end_char": s["end_char"],
                       "raw": s["raw"], "clean": s["clean"], "compressed": s["compressed"],
                       "decision": s["decision"], "citations_stripped": s["citations"], "stats": s["stats"]}
                      for s in survivors],
        "dropped": dropped,
        "sections_detected": sr.sections_detected,
        "fallbacks": fallbacks,
    }
    counts = {
        "total": len(sents), "kept": len(survivors), "filter": n_filter,
        "cited_background": sum(1 for d in dropped if d["reason"] == "cited_background"),
        "own_cue_stripped": sum(1 for s in survivors if s["decision"] == "own_cue_stripped"),
    }
    report = _report_row(slug, meta, tok, counts, sr.sections_detected, fallbacks)
    return PaperResult(slug, txt, sidecar, report)
