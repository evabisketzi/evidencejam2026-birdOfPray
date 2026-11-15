"""Code-only options ported from camo_pipeline (all default off, so the default output is byte-identical).

  --fit-attributes   life-stage words leave the measured attribute and go to life_stage (+ life_stage_term for rosette and
                     sapling); a leading direction word ("increased cover") goes to the qualifier.  'seedling number',
                     'rosette number' and 'number of individuals' + stage become the same variable, and the attribute is the
                     bare word the ontology lookup needs (ontology/GROUNDING.md, EXTRACTION_RULES).   (camo fit.fit_attribute)
  --double-negative  'prevents' with a 'decreased' object is the model writing the direction twice ("planting prevented
                     invasion" -> p + invasion/-): the edge becomes 'causes' + decreased.             (camo fit.fit_finding R1)
  --provenance       annotator (camo_agent:<model>) on nodes and edges, annotation_timestamp on edges and variable_key on
                     nodes (entity_term | measured_attribute | applied_to: the same variable across papers).
                                                                              (camo assemble.camo_node, fit.variable_key)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .parse import Var


@dataclass(frozen=True)
class Features:
    fit_attributes: bool = False
    double_negative: bool = False
    provenance: bool = False

    @classmethod
    def from_names(cls, names) -> "Features":
        """'fit-attributes,provenance' (or an iterable of names) -> Features; unknown names raise ValueError."""
        if isinstance(names, str):
            names = [n for n in re.split(r"[,\s]+", names) if n]
        flags = {n.replace("-", "_") for n in names or []}
        unknown = flags - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown feature(s): {', '.join(sorted(unknown))}")
        return cls(**{f: True for f in flags})


OFF = Features()

# ----------------------------------------------------------------------------------------------- --fit-attributes
_STAGE_WORDS = {   # word in the attribute -> the pipeline's stage code (expand.STAGE_ENUM)
    "seedling": "seedling", "seedlings": "seedling", "germinant": "seedling", "germinants": "seedling",
    "sapling": "juvenile", "saplings": "juvenile", "rosette": "juvenile", "rosettes": "juvenile",
    "juvenile": "juvenile", "juveniles": "juvenile", "ramet": "ramet", "ramets": "ramet", "adult": "adult", "adults": "adult",
}
_STAGE_TERM_WORDS = {"sapling": "sapling", "saplings": "sapling", "rosette": "rosette", "rosettes": "rosette"}
_DIRECTION_WORDS = {"increased": "+", "increase": "+", "higher": "+", "greater": "+", "enhanced": "+", "improved": "+",
                    "decreased": "-", "decrease": "-", "lower": "-", "reduced": "-", "reduction": "-", "declined": "-"}
_COUNT_ATTRS = {"number", "numbers", "number of", "count", "counts", "no.", "individuals", "plants"}


def fit_attribute(prop: Optional[str], change: Optional[str], stage: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """-> (attribute, change, stage code, life_stage_term).  Nothing changes when the attribute has no stage or direction
    word.  A stage already given (stage= key) wins over one found in the attribute."""
    if not prop:
        return prop, change, stage, None
    words, kept, stage_term, had_stage = prop.split(), [], None, False
    for w in words:
        bare = w.strip(",()").lower()
        if bare in _STAGE_WORDS:
            had_stage = True
            stage = stage or _STAGE_WORDS[bare]
            stage_term = stage_term or _STAGE_TERM_WORDS.get(bare)
            continue
        kept.append(w)
    if kept and kept[0].lower() in _DIRECTION_WORDS:
        change = change or _DIRECTION_WORDS[kept[0].lower()]
        kept = kept[1:]
    if not had_stage and len(kept) == len(words):
        return prop, change, stage, None                    # untouched (the common case)
    a = " ".join(kept)
    a = re.sub(r"^(?:in|of|the)\s+|\s+(?:of|per|in)$", "", a, flags=re.I).strip(" ,")
    if a.lower() in _COUNT_ATTRS or (not a and had_stage):
        a = "number of individuals"                         # 'seedlings', 'rosette number' -> a count of individuals
    return a or None, change, stage, stage_term


def fit_var(var: Var, stage: Optional[str]) -> Tuple[Var, Optional[str], Optional[str]]:
    prop, change, stage, stage_term = fit_attribute(var.prop, var.change, stage)
    return Var(var.thing, prop, change, var.vtype), stage, stage_term


# ----------------------------------------------------------------------------------------------- --double-negative
def repair_double_negative(edge: dict, nodes: Dict[str, dict]) -> Optional[str]:
    o = nodes.get(edge.get("object")) or {}
    if edge.get("predicate") == "prevents" and o.get("state_or_change_qualifier") == "decreased" and not edge.get("negated"):
        edge["predicate"] = "causes"
        return "prevents+decreased->causes"
    return None


# ----------------------------------------------------------------------------------------------- --provenance
_AGENT = re.compile(r"[^A-Za-z0-9._-]+")


def agent_id(model: str) -> str:
    """camo_agent:<model>, in the form the schema pattern accepts (camo_agent:[A-Za-z0-9._-]+)."""
    return "camo_agent:" + (_AGENT.sub("-", model or "").strip("-") or "llm")


def _light(t: str) -> str:
    t = str(t or "")
    return t if ":" in t and " " not in t else " ".join(re.sub(r"[^a-z0-9µ.%/ -]+", " ", t.lower()).split())


def variable_key(node: dict) -> str:
    applied = ";".join(sorted(_light(a.get("entity_term")) for a in node.get("applied_to") or []))
    return "|".join([_light(node.get("entity_term")), _light(node.get("measured_attribute")), applied])


def add_provenance(nodes: Dict[str, dict], edges: List[dict], model: str, timestamp: str) -> None:
    """In place.  Run last (after the ontology stage), so variable_key carries the final entity_term / attribute."""
    who = agent_id(model)
    for n in nodes.values():
        n["variable_key"] = variable_key(n)
        n["annotator"] = who
    for e in edges:
        e["annotator"] = who
        e["annotation_timestamp"] = timestamp
