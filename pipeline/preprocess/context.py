"""Step 8: background block (never numbered, so it cannot be annotated).

Design sentences from the Methods (site, treatments, replication, timing) plus the Introduction's aims
paragraph, capped at a configurable token budget.  Earlier sentences and design-cue matches are preferred.
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, List

from .classify import find_citations, strip_citations
from .sentences import split_sentences
from .stats import compress_stats

DESIGN_CUES = re.compile(
    r"\b(?:sites?|located|randomi[sz]ed|blocks?|blocked|plots?|quadrats?|transects?|controls?|treatments?|planted|"
    r"transplanted|seeded|burn(?:ed|ing|s)?|removed|fenced|densit(?:y|ies)|years?|sampled|sampling|measured|surveyed|"
    r"replicat\w*|spring|summer|autumn|fall|winter|season\w*|experiment\w*|design|stands?|hectares?|ha)\b",
    re.I,
)


def _prep(sentence: str, alpha: float) -> str:
    s = strip_citations(sentence, find_citations(sentence))
    s, _ = compress_stats(s, alpha)
    return s


def build_context(aims: str, methods_text: Iterable[str], count_tokens: Callable[[str], int],
                  alpha: float = 0.05, budget: int = 400) -> str:
    """Return the CONTEXT string ('' when budget is 0 or nothing qualifies)."""
    if budget <= 0:
        return ""
    aim_sents = [_prep(s, alpha) for s in split_sentences(aims)] if aims else []
    aim_sents = [s for s in aim_sents if len(s) > 20]
    meth: List[str] = []
    for para in methods_text:
        for s in split_sentences(para):
            if len(s) < 25 or not DESIGN_CUES.search(s):
                continue
            meth.append(_prep(s, alpha))
    aim_budget = min(sum(count_tokens(s) for s in aim_sents), budget // 3)
    chosen_aims: List[str] = []
    used = 0
    for s in aim_sents:
        c = count_tokens(s)
        if used + c <= aim_budget:
            chosen_aims.append(s)
            used += c
    chosen_meth: List[str] = []
    for s in meth:
        c = count_tokens(s)
        if used + c <= budget:
            chosen_meth.append(s)
            used += c
    return " ".join(chosen_aims + chosen_meth).strip()
