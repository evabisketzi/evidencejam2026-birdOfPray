"""--preprocess sentence-chunks: our sentence filter (unchanged), sent as one LLM call per chunk of about CHUNK_TOKENS of
numbered sentences, split at section boundaries, with the TITLE / SPECIES / CONTEXT header repeated in every chunk.
The sentences and their numbers are exactly those of --preprocess sentence; only the grouping into calls differs."""
from __future__ import annotations

import re
from typing import Callable, Dict, List

from .assemble import Options, PaperResult, process_paper

CHUNK_TOKENS = 2500
_LINE = re.compile(r"^\[(\d+)\] \((\w+)\) ")


def split_body(lines: List[str], count: Callable[[str], int], budget: int = CHUNK_TOKENS) -> List[List[str]]:
    """Greedy: whole sections while they fit; a section larger than the budget is split between sentences."""
    sections: List[List[str]] = []
    for ln in lines:
        m = _LINE.match(ln)
        sec = m.group(2) if m else None
        if sections and sections[-1] and _LINE.match(sections[-1][-1]) and _LINE.match(sections[-1][-1]).group(2) == sec:
            sections[-1].append(ln)
        else:
            sections.append([ln])
    chunks: List[List[str]] = []
    cur: List[str] = []
    cur_tok = 0
    for sec in sections:
        t = count("\n".join(sec))
        if cur and cur_tok + t > budget:
            chunks.append(cur); cur, cur_tok = [], 0
        if t <= budget:
            cur += sec; cur_tok += t
            continue
        for ln in sec:                                          # oversized section: split between sentences
            lt = count(ln)
            if cur and cur_tok + lt > budget:
                chunks.append(cur); cur, cur_tok = [], 0
            cur.append(ln); cur_tok += lt
    if cur:
        chunks.append(cur)
    return chunks


def process_paper_sentence_chunks(slug: str, raw: str, meta: Dict[str, str], count, opts: Options, taxon_table=None) -> PaperResult:
    base = process_paper(slug, raw, meta, count, opts, taxon_table)
    if "TEXT:\n" not in base.txt:
        return base
    head, body = base.txt.split("TEXT:\n", 1)
    lines = [ln for ln in body.splitlines() if ln.strip()]
    groups = split_body(lines, count)
    if len(groups) <= 1:
        return base                                             # short paper: one call, identical to --preprocess sentence
    side = dict(base.sidecar)
    side["chunk_texts"] = [head + "TEXT:\n" + "\n".join(g) + "\n" for g in groups]
    rep = dict(base.report)
    rep["chunks"] = len(groups)
    return PaperResult(slug, base.txt, side, rep)
