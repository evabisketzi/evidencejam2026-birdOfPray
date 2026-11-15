"""--study (default off): one short call per paper for study-level facts, ported from camo_pipeline (prompts.STUDY_*,
run.extract_article).

Input: the TITLE and CONTEXT block the extraction prompt already carries (aims + study-design sentences, <= ~400 tokens).
Output (each key only when the text states it; checked here, never guessed):
  source_documents: study_design (EvidenceTypeEnum), study_country, study_state_or_province, study_period_start / _end
                    (ISO year, year-month or date), study_duration_months
  edges:            evidential_basis.evidence_types takes the study design when it is of the same family as the per-claim
                    design the model gave (an 'exp' claim in a randomized experiment -> randomized_experiment), instead of the
                    regex guess in expand.edge_fields.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_YAML = ROOT / "schema" / "causalmosaic.yaml"
MAX_TOKENS = 150
CACHE_SALT = "study-1"

SYSTEM = """You read the title and the study-design notes of an ecology paper and return study-level facts for a program. Return minified JSON only. Omit a key when the text does not state it; never guess.

design  the study design: randomized_experiment (treatments assigned at random, incl. randomized blocks) | quasi_experiment (manipulation without randomization, before-after, BACI) | natural_experiment (an unplanned event is the treatment) | observational_longitudinal (repeated surveys, chronosequence) | observational_cross_sectional (one-time survey, site comparison) | mechanistic_study (greenhouse, lab or physiological test of a pathway) | structural_equation_model | meta_analysis | systematic_review | modeling_simulation | case_study | expert_judgment | theoretical | practitioner_experience | indigenous_knowledge
country, region   where the fieldwork was done (country name; state or province).
start, end        first and last year of data collection, e.g. "2001", "2004".
months            study duration in months, as a number.

Example: {"design":"randomized_experiment","country":"Canada","region":"Ontario","start":"2001","end":"2003","months":36}"""

# claim design code (parse.py) -> the EvidenceTypeEnum values of the same family
FAMILY = {"exp": {"randomized_experiment", "quasi_experiment", "natural_experiment"},
          "obs": {"observational_longitudinal", "observational_cross_sectional"},
          "rev": {"meta_analysis", "systematic_review"},
          "mod": {"modeling_simulation", "structural_equation_model"}}
_SYN = {"randomized": "randomized_experiment", "randomised_experiment": "randomized_experiment", "rct": "randomized_experiment",
        "experiment": "randomized_experiment", "quasi": "quasi_experiment", "baci": "quasi_experiment",
        "before_after": "quasi_experiment", "longitudinal": "observational_longitudinal",
        "chronosequence": "observational_longitudinal", "cross_sectional": "observational_cross_sectional",
        "observational": "observational_cross_sectional", "survey": "observational_cross_sectional",
        "meta-analysis": "meta_analysis", "review": "systematic_review", "model": "modeling_simulation",
        "simulation": "modeling_simulation", "sem": "structural_equation_model"}
_DATE = re.compile(r"^(1[6-9]|20)\d\d(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")


@lru_cache(maxsize=1)
def evidence_types() -> Tuple[str, ...]:
    s = yaml.safe_load(SCHEMA_YAML.read_text(encoding="utf-8"))
    return tuple((s["enums"]["EvidenceTypeEnum"].get("permissible_values") or {}).keys())


def user_text(title: str, context: str) -> str:
    return f"TITLE: {title}\nTEXT: {context}\nReturn the study-level facts as minified JSON only."


def parse_reply(text: str) -> dict:
    """Model reply -> checked facts (keys of source_documents).  Anything unparseable or out of range is left out."""
    m = re.search(r"\{.*\}", re.sub(r"<think>.*?</think>", "", text or "", flags=re.S), re.S)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except ValueError:
        obj = {}
    if not isinstance(obj, dict):
        return {}
    out: dict = {}
    d = str(obj.get("design") or "").strip().lower().replace(" ", "_")
    d = d if d in evidence_types() else _SYN.get(d)
    if d in evidence_types():
        out["study_design"] = d
    for src, dst in (("country", "study_country"), ("region", "study_state_or_province")):
        v = str(obj.get(src) or "").strip()
        if 1 < len(v) <= 120 and v.lower() not in ("null", "none", "unknown", "not stated", "n/a"):
            out[dst] = v
    for src, dst in (("start", "study_period_start"), ("end", "study_period_end")):
        v = str(obj.get(src) or "").strip()
        if _DATE.match(v):
            out[dst] = v
    if "study_period_start" in out and "study_period_end" in out and out["study_period_end"][:4] < out["study_period_start"][:4]:
        out.pop("study_period_end")
    try:
        months = float(obj.get("months"))
        if 0 < months < 2400:
            out["study_duration_months"] = months
    except (TypeError, ValueError):
        pass
    return out


def study_facts(client, title: str, context: str, label: str = "") -> Tuple[dict, Dict[str, int]]:
    """-> (facts, tokens).  No context or a failed call -> ({}, ...): the paper simply gets no study fields."""
    tokens = {"prompt_tokens": 0, "completion_tokens": 0}
    if not (context or "").strip():
        return {}, tokens
    try:
        r = client.complete(SYSTEM, user_text(title, context), label)
    except Exception as e:  # noqa: BLE001 - optional metadata must never fail a paper
        log.warning("%s: study call failed (%s)", label or "-", e)
        return {}, tokens
    if not r.cached:
        tokens = {"prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens}
    return parse_reply(r.text), tokens


def apply_design(edges: List[dict], design: Optional[str]) -> int:
    """evidence_types <- the study design where it is of the same family as the per-claim guess (expand.edge_fields maps the
    claim design to one member of its family, e.g. exp -> randomized_experiment or quasi_experiment).  Returns edges changed."""
    if not design:
        return 0
    n = 0
    for e in edges:
        basis = e.get("evidential_basis") or {}
        cur = (basis.get("evidence_types") or [None])[0]
        fam = next((f for f in FAMILY.values() if cur in f), None)
        if fam and design in fam and basis["evidence_types"] != [design]:
            basis["evidence_types"] = [design]
            n += 1
    return n


def make_client(base_cfg, Client):
    cfg = copy.copy(base_cfg)
    cfg.max_tokens, cfg.cache_salt = MAX_TOKENS, CACHE_SALT
    return Client(cfg)
