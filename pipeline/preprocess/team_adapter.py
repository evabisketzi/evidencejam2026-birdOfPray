"""Alternative stage 1: the teammate's paragraph preprocessing (team_paper.py = preprocess_paper.py from team/main, verbatim),
adapted to our extraction input.

Only the TEXT lines change.  TITLE, SPECIES and CONTEXT are taken from our own stage 1, so a comparison measures the paragraph
cleaning / selection and nothing else.  The paragraphs that route 'extract' are split into sentences with the teammate's splitter,
numbered, and mapped back to raw-markdown offsets through Paragraph.to_original (same offset convention as ours).
The teammate's cleaning already removes inline citations and formatting, so we neither drop cited-background sentences nor compress statistics here.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from . import team_paper as T
from .assemble import PaperResult, process_paper

log = logging.getLogger(__name__)

TAG = {"abstract": "abs", "highlights": "abs", "results": "res", "discussion": "dis", "conclusion": "con",
       "front": "res", "unknown": "res"}


def process_paper_team(slug: str, raw: str, meta: Dict[str, str], count: Callable[[str], int], opts, taxon_table: Optional[Dict[str, int]] = None,
                       min_score: float = 3.0, chunk_tokens: Optional[int] = None) -> PaperResult:
    """chunk_tokens=None: one input with every kept sentence (whole paper, one call).
    chunk_tokens=N: the teammate's pack() groups the paragraphs into balanced chunks of <= N tokens; each chunk becomes its own LLM
    call (sidecar['chunk_texts']), with the same TITLE/SPECIES/CONTEXT header and globally numbered sentences."""
    base = process_paper(slug, raw, meta, count, opts, taxon_table)          # our header (TITLE / SPECIES / CONTEXT) and report row
    try:
        res = T.preprocess(raw, tokenizer=count, source=slug, config=T.Config(min_score=min_score,
                                                                        keep_results_prose=bool(getattr(opts, "keep_results", False))))
        sents: List[dict] = []
        if chunk_tokens:
            pk = T.pack(res, T.PackConfig(max_chunk_tokens=chunk_tokens), tokenizer=count)
            groups = [(k, [pk.units[i] for i in c.paragraph_ids]) for k, c in enumerate(pk.chunks)]
        else:
            groups = [(0, [p for p in res.paragraphs if p.route == "extract"])]
        for k, pars in groups:
            for p in pars:
                for a, b in T.sentence_spans(p.text):
                    text = p.text[a:b].strip()
                    if len(text) < 3:
                        continue
                    aa = a + (len(p.text[a:b]) - len(p.text[a:b].lstrip()))
                    rs, re_ = p.to_original(aa, aa + len(text))
                    sents.append({"section": TAG.get(p.section, "res"), "start_char": rs, "end_char": re_, "raw": raw[rs:re_],
                                  "clean": text, "compressed": text, "decision": "team", "citations_stripped": [], "stats": [], "chunk": k})
        if not sents:
            raise RuntimeError("team preprocessing kept no sentences")
    except Exception as e:  # noqa: BLE001 - never lose a paper
        log.warning("%s: team preprocessing failed (%r); using our own stage 1", slug, e)
        base.sidecar["fallbacks"] = list(base.sidecar.get("fallbacks", [])) + ["team_preprocess"]
        return base
    for i, s in enumerate(sents, 1):
        s["n"] = i
    head = base.txt.split("TEXT:\n", 1)[0]
    txt = head + "TEXT:\n" + "\n".join(f"[{s['n']}] ({s['section']}) {s['compressed']}" for s in sents) + "\n"
    side = dict(base.sidecar)
    side["sentences"] = sents
    if chunk_tokens:
        texts = []
        for k in sorted({s["chunk"] for s in sents}):
            body = "\n".join(f"[{s['n']}] ({s['section']}) {s['compressed']}" for s in sents if s["chunk"] == k)
            texts.append(head + "TEXT:\n" + body + "\n")
        side["chunk_texts"] = texts
    side["dropped"] = [{"reason": d.get("reason"), "section": d.get("section"), "start_char": d.get("orig_start"),
                        "end_char": d.get("orig_end"), "clean": d.get("preview", "")} for d in res.dropped]
    rep = dict(base.report)
    rep["tokens_final"] = count(txt)
    rep["sentences_kept"] = len(sents)
    return PaperResult(slug, txt, side, rep)


def process_paper_team_chunks(slug, raw, meta, count, opts, taxon_table=None):
    """Paragraph selection + one LLM call per paragraph chunk (pack(), default 2,500 tokens of paragraph text per chunk)."""
    return process_paper_team(slug, raw, meta, count, opts, taxon_table, chunk_tokens=getattr(opts, "chunk_tokens", None) or CHUNK_TOKENS)


CHUNK_TOKENS = 2500
