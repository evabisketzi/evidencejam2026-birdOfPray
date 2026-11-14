"""Gated matching.

Levels (each evaluated on the pairs assigned below):
  loose    subject AND object entities agree, and the null flags agree
  standard loose AND object-attribute similarity >= threshold AND object directions not opposite (UP vs DOWN)
  strict   standard AND object direction groups equal
The subject's attribute is never gated.  The one-to-one Hungarian assignment runs only over pairs that pass loose and
maximises  0.6 * object_attr + 0.2 * subject_sim + 0.2 * direction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from .load import EdgeRec
from .normalise import NodeSig, jaccard

W_ATTR, W_SUBJ, W_DIR = 0.6, 0.2, 0.2
DEFAULT_THRESHOLD = 0.5


# ----------------------------------------------------------------------------------------------- entities
def entity_agree(a: NodeSig, b: NodeSig) -> bool:
    """Same organism / entity?  entity_type is never consulted."""
    if a.has_taxon and b.has_taxon:
        return bool((a.taxa_ids & b.taxa_ids) or (a.taxa_text & b.taxa_text))
    if (not a.entity_text) != (not b.entity_text):
        return False                      # one side says nothing about the entity
    return jaccard(a.entity_text, b.entity_text) >= 0.5


def taxon_component(a: NodeSig, b: NodeSig) -> float:
    """Graded version of entity_agree (used for display and as the subject's soft similarity)."""
    if a.has_taxon and b.has_taxon:
        return 1.0 if entity_agree(a, b) else 0.0
    return jaccard(a.entity_text, b.entity_text)


# ----------------------------------------------------------------------------------------------- attribute
def attr_sim(a: NodeSig, b: NodeSig) -> float:
    """Similarity of the two measured attributes after synonym mapping (the node name is not consulted unless an
    attribute ID has no known label, or an attribute is missing)."""
    if a.attr_id and a.attr_id == b.attr_id:
        return 1.0
    if a.attr_tokens and b.attr_tokens:
        return jaccard(a.attr_tokens, b.attr_tokens)
    if a.attr_id and b.attr_id:
        return 0.0                         # two different IDs, at least one unlabelled: cannot be shown equal
    return jaccard(a.descriptor, b.descriptor)


def direction_component(a: NodeSig, b: NodeSig) -> float:
    if a.direction == b.direction:
        return 1.0
    if a.direction in ("NONE", "OCCUR") or b.direction in ("NONE", "OCCUR"):
        return 0.5
    return 0.0


def opposite(a: NodeSig, b: NodeSig) -> bool:
    return {a.direction, b.direction} == {"UP", "DOWN"}


def subject_sim(a: NodeSig, b: NodeSig) -> float:
    """Soft similarity of the subjects (attribute included but never gated)."""
    return 0.5 * taxon_component(a, b) + 0.3 * attr_sim(a, b) + 0.2 * direction_component(a, b)


def loose_pass(g: EdgeRec, p: EdgeRec) -> bool:
    return g.null == p.null and entity_agree(g.subj, p.subj) and entity_agree(g.obj, p.obj)


def near_sim(g: EdgeRec, p: EdgeRec) -> float:
    """Ungated closeness, used only to name the nearest candidate in the error lists."""
    if g.null != p.null:
        return 0.0
    return (0.45 * (0.5 * taxon_component(g.subj, p.subj) + 0.3 * attr_sim(g.subj, p.subj) + 0.2 * direction_component(g.subj, p.subj))
            + 0.45 * (0.5 * taxon_component(g.obj, p.obj) + 0.3 * attr_sim(g.obj, p.obj) + 0.2 * direction_component(g.obj, p.obj)) + 0.10)


# ----------------------------------------------------------------------------------------------- documents
@dataclass(frozen=True)
class Pair:
    i: int                  # gold index
    j: int                  # predicted index
    obj_attr: float
    subj_sim: float
    direction: float
    opposite: bool
    dir_equal: bool
    score: float            # the assignment objective


@dataclass
class DocMatch:
    G: List[EdgeRec]
    P: List[EdgeRec]
    pairs: List[Pair]                  # assigned pairs that pass loose
    near: np.ndarray                   # ungated closeness matrix (gold x pred), for the error lists
    loose_ok: np.ndarray               # boolean matrix: which pairs pass the loose gate
    threshold: float

    def level(self, name: str, threshold: float = None) -> List[Pair]:
        t = self.threshold if threshold is None else threshold
        if name == "loose":
            return list(self.pairs)
        std = [p for p in self.pairs if p.obj_attr >= t and not p.opposite]
        return std if name == "standard" else [p for p in std if p.dir_equal]


def match_document(G: Sequence[EdgeRec], P: Sequence[EdgeRec], threshold: float = DEFAULT_THRESHOLD) -> DocMatch:
    G, P = list(G), list(P)
    n, m = len(G), len(P)
    loose = np.zeros((n, m), dtype=bool)
    obj = np.zeros((n, m))
    subj = np.zeros((n, m))
    dirs = np.zeros((n, m))
    near = np.zeros((n, m))
    for i, g in enumerate(G):
        for j, p in enumerate(P):
            near[i, j] = near_sim(g, p)
            if loose_pass(g, p):
                loose[i, j] = True
                obj[i, j] = attr_sim(g.obj, p.obj)
                subj[i, j] = subject_sim(g.subj, p.subj)
                dirs[i, j] = direction_component(g.obj, p.obj)
    score = np.where(loose, W_ATTR * obj + W_SUBJ * subj + W_DIR * dirs, 0.0)
    pairs: List[Pair] = []
    if n and m:
        r, c = linear_sum_assignment(-score)
        for i, j in zip(r, c):
            if loose[i, j]:
                pairs.append(Pair(int(i), int(j), float(obj[i, j]), float(subj[i, j]), float(dirs[i, j]),
                                  opposite(G[i].obj, P[j].obj), G[i].obj.direction == P[j].obj.direction, float(score[i, j])))
    return DocMatch(G, P, pairs, near, loose, threshold)
