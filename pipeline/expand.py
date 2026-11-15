"""Stage 4b: parsed claim lines -> CAMO nodes and edges (plain dicts that follow schema/causalmosaic.yaml)."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import grounding
from .parse import Claim, Var, parse_var
from .preprocess.abbrev import expand_abbreviations

log = logging.getLogger(__name__)

PRED_ENUM = {"c": "causes", "ct": "contributes_to", "p": "prevents", "e": "enables", "d": "disrupts", "a": "associated_with",
             "cw": "correlated_with", "pr": "precedes"}
LANG_ENUM = {"D": "direct_causal", "U": "uncertain_causal", "A": "associational"}
CHANGE_ENUM = {"+": "increased", "-": "decreased", "=": "unchanged", "pres": "present", "abs": "absent", "intro": "introduced",
               "rem": "removed", "occ": "occurred"}
_ADJ = {"+": "Increased", "-": "Decreased", "=": "Stable"}
_NOUN = {"pres": "Presence of", "abs": "Absence of", "intro": "Introduction of", "rem": "Removal of", "occ": "Occurrence of"}
TYPE_ENUM = {"tax": "taxon", "var": "environmental_variable", "com": "composite_variable", "proc": "environmental_process",
             "mgmt": "management_intervention"}
STAGE_ENUM = {"seed": "seed_or_seed_bank", "seedling": "germinant_or_seedling", "juvenile": "juvenile",
              "ramet": "ramet_or_clonal_unit", "adult": "reproductive_adult"}
SECTION_ENUM = {"abs": "abstract", "res": "results", "dis": "discussion", "con": "conclusion", "lim": "discussion"}
SEASONS = {"early_spring", "mid_spring", "late_spring", "spring", "early_summer", "summer", "autumn", "winter", "growing_season",
           "dormant_season"}
DOSE_LEVELS = {"low", "intermediate", "high"}

_ACTION = ("planting", "removal", "burning", "mowing", "seeding", "grazing", "fencing", "exclosure", "thinning", "herbicide",
           "restoration", "transplant", "fertili", "rewetting", "harvest", "logging", "clipping", "outplant", "weeding",
           "irrigation", "cutting", "scarification", "translocation", "reintroduction")
_PROCESS = ("competition", "invasion", "granivory", "herbivory", "predation", "decomposition", "succession", "leafing",
            "flowering", "dispersal", "browsing", "parasitism", "mortality process")
_GUILD = ("species", "community", "communities", "natives", "guild", "assemblage", "plants", "vegetation")

_COMPARE = re.compile(r"\b(than|compared|versus|vs\.?|more|less|higher|lower)\b", re.I)
_MECH = re.compile(r"\b(because|through|via|mechanism|deprived|allowing)\b", re.I)
_PROB = re.compile(r"\b(usually|tend|tends|tended|often|probab\w*)\b", re.I)
_AGENCY = re.compile(r"\b(should|recommend\w*|strategy|managers?|effective)\b", re.I)
# causal-language calibration: the model labels hedged sentences ("It appears that ...", "The results suggest ...", "would be
# effective") as direct_causal.  Checked on the four gold papers (cached model output): this narrow list moves the language mix
# toward the gold on all four; broader lists (likely, probably, indicated, generally) and a rule on observational designs made it
# worse, because the human annotators treat those as direct (Murphy) or as associational (observational papers).
_HEDGE = re.compile(r"\b(may|might|could|would|appears?|appeared|seems?|seemed|suggests?|suggested|suggesting)\b", re.I)
_CONTINGENT = re.compile(r"\b(if|when|under|unless)\b", re.I)
_PROTO = re.compile(r"\b(usually|generally|often)\b", re.I)
_CTRL = re.compile(r"control|uncaged|unburned|untreated|reference|open", re.I)
_DOSE_WORDS = re.compile(r"density|dose|level|rate", re.I)
_P_EXACT = re.compile(r"\b[Pp]\s*=\s*(\d*\.\d+|\d+(?:\.\d+)?)")
_METHODS = [(re.compile(r"\bMANOVA\b|\bMANOVAR\b", re.I), "manova"), (re.compile(r"\br?ANOVA\b|\banalys[ei]s of variance\b", re.I), "anova"),
            (re.compile(r"\bGLMM\b|\bLMM\b|\bmixed[- ](?:effects?|model)", re.I), "mixed_model"),
            (re.compile(r"\bWilcoxon\b|\bKruskal\b|\bMann[- ]Whitney\b", re.I), "nonparametric"),
            (re.compile(r"\bregression\b|\bR\s*2\b|\bR²", re.I), "regression")]
_TCODE = re.compile(r"\bT(\d+)\b")


@dataclass
class Expanded:
    nodes: Dict[str, dict] = field(default_factory=dict)
    edges: List[dict] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s and not re.match(r"[a-z]+[A-Z]", s) else s     # keep 'pH', 'eDNA', 'mRNA'


class Expander:
    def __init__(self, slug: str, side: dict):
        self.slug = slug
        self.side = side
        self.sent = {int(s["n"]): s for s in side.get("sentences", [])}
        self.species = {sp["id"]: sp for sp in side.get("species", [])}
        self.abbrev = side.get("abbreviations") or {}
        self.context = (side.get("context") or "")
        self.alltext = " ".join(s.get("clean") or "" for s in self.sent.values()) + " " + self.context
        self.out = Expanded()
        self.n_edge = 0

    # ------------------------------------------------------------------ things
    def taxon(self, tcode: str) -> Tuple[Optional[str], str]:
        """(NCBITaxon id or None, readable name) for a T-code."""
        sp = self.species.get(tcode)
        if not sp:
            self.out.stats["unknown_tcode"] = self.out.stats.get("unknown_tcode", 0) + 1
            return None, tcode
        return (sp.get("ncbitaxon") or grounding.taxon_id(sp["name"])), sp["name"]

    def resolve(self, thing: str) -> Tuple[str, str, Optional[str], Optional[str]]:
        """-> (kind, readable text, entity word, taxon id)  kind: taxon | action | noun"""
        t = thing.strip()
        m = re.fullmatch(r"T(\d+)", t)
        if m:
            tid, name = self.taxon("T" + m.group(1))
            return "taxon", name, tid or name, tid
        m = re.fullmatch(r"(.+?)\s*\(\s*T(\d+)\s*\)", t)
        if m:
            tid, name = self.taxon("T" + m.group(2))
            word = m.group(1).strip()
            return "action", f"{word} of {name}", word, tid or name
        txt = _TCODE.sub(lambda mm: self.taxon("T" + mm.group(1))[1], t)
        return "noun", txt, txt, None

    # ------------------------------------------------------------------ spans
    def spans(self, numbers: List[int]) -> List[dict]:
        out = []
        for n in numbers:
            s = self.sent.get(n)
            if not s:
                continue
            sp = {"text": s.get("clean") or s.get("raw") or ""}
            if s.get("start_char") is not None:
                sp["start_char"], sp["end_char"] = int(s["start_char"]), int(s["end_char"])
            sec = SECTION_ENUM.get(s.get("section"))
            if sec:
                sp["section"] = sec
            if sp["text"]:
                out.append(sp)
        return out

    # ------------------------------------------------------------------ nodes
    def entity_type(self, var: Var, kind: str, word: str) -> str:
        if var.vtype:
            return TYPE_ENUM[var.vtype]
        if kind == "taxon":
            return "taxon"
        w = (word or "").lower()
        if any(a in w for a in _ACTION):
            return "management_intervention"
        if any(p in w for p in _PROCESS):
            return "environmental_process"
        if any(re.search(rf"\b{g}\b", w) for g in _GUILD):
            return "composite_variable"
        return "environmental_variable"

    def node(self, var: Var, stage: Optional[str], spans: List[dict], null_effect: bool = False) -> str:
        kind, text, word, tid = self.resolve(var.thing)
        change = var.change
        if null_effect and change == "=":
            change = None                              # never 'unchanged' on a null result
        key = (var.key(stage), null_effect and var.change == "=")
        nid = f"node:{self.slug}_{hashlib.sha1(repr(key).encode()).hexdigest()[:10]}"
        node = self.out.nodes.get(nid)
        if node is None:
            if kind == "taxon":
                entity_term = tid or text
                applied = None
            elif kind == "action":
                entity_term = grounding.term_id(word, "entity") or word
                applied = [{"entity_type": "taxon", "entity_term": tid or text.split(" of ", 1)[-1]}]
            else:
                entity_term = grounding.term_id(word, "entity") or word
                applied = None
            prop = expand_abbreviations(var.prop, self.abbrev) if var.prop else var.prop
            # name from the model's own words first (keeps the name templates), then paper-defined abbreviations expanded:
            # 'Soil VMC' -> 'Soil volumetric moisture content (VMC)'
            name = expand_abbreviations(compose_name(change, var.prop, text), self.abbrev)
            node = {"id": nid, "name": _cap(name), "entity_type": self.entity_type(var, kind, word), "entity_term": entity_term}
            if prop:
                node["measured_attribute"] = (grounding.term_id(prop, "attribute") or grounding.term_id(var.prop, "attribute")
                                              or prop)
            if change:
                node["state_or_change_qualifier"] = CHANGE_ENUM[change]
            if applied:
                node["applied_to"] = applied
            if stage in STAGE_ENUM:
                node["life_stage"] = STAGE_ENUM[stage]
            node["source_spans"] = []
            self.out.nodes[nid] = node
        for sp in spans:
            if sp not in node["source_spans"] and len(node["source_spans"]) < 6:
                node["source_spans"].append(sp)
        return nid

    # ------------------------------------------------------------------ edge parts
    @staticmethod
    def parse_dose(v: str) -> Optional[dict]:
        m = re.match(r"^\s*(as little as|at least|above|over|more than|>=?|below|under|less than|up to|<=?)?\s*(-?\d+(?:\.\d+)?)"
                     r"(?:\s*[-–]\s*(-?\d+(?:\.\d+)?))?\s*(.*)$", v, re.I)
        if not m:
            return None
        pre, a, b, unit = (m.group(1) or "").lower(), float(m.group(2)), m.group(3), m.group(4).strip()
        d: dict = {}
        if b is not None:
            d["minimum_value"], d["maximum_value"] = a, float(b)
        elif pre in ("below", "under", "less than", "up to", "<", "<="):
            d["maximum_value"] = a
        elif pre:
            d["minimum_value"] = a
        else:
            d["numeric_value"] = a
        if unit:
            d["unit_text"] = unit
        d["verbatim"] = v.strip()
        return d

    def edge_fields(self, claim: Claim, spans: List[dict], text: str, comp_text: str) -> dict:
        k = claim.keys
        null = claim.kind == "N"
        e: dict = {}
        if null:
            e["negated"] = True
            e["causal_language"] = "no_relationship"
        else:
            lang = claim.language or ("associational" if claim.predicate in ("a", "cw", "pr") else "U")
            e["causal_language"] = calibrate_language(LANG_ENUM.get(lang, lang if lang in LANG_ENUM.values() else "uncertain_causal"),
                                                      claim.design, text)
        e["original_sentence"] = spans[0]["text"] if spans else text
        # philosophical accounts (at least one)
        acc = []
        if claim.design == "exp":
            acc.append("interventionist")
        if k.get("vs") or _COMPARE.search(text):
            acc.append("counterfactual")
        if k.get("med") or _MECH.search(text):
            acc.append("mechanistic")
        if _PROB.search(text):
            acc.append("probabilistic")
        if claim.design == "jud" or _AGENCY.search(text):
            acc.append("agency")
        e["philosophical_accounts"] = acc or ["regularity"]
        # strength
        if "[sig]" in comp_text:
            sig = "significant"
        elif "[ns]" in comp_text:
            sig = "not_significant"
        elif null:
            sig = "not_significant"
        elif e["causal_language"] == "uncertain_causal":
            sig = "not_tested"
        else:
            sig = "not_reported"
        strength = {"status": "explicitly_asserted", "significance": sig}
        m = _P_EXACT.search(text)
        if m:
            try:
                strength["p_value"] = float(m.group(1))
            except ValueError:
                pass
        for rx, name in _METHODS:
            if rx.search(text):
                strength["analysis_method"] = name
                break
        e["strength"] = strength
        if claim.design == "exp":
            e["direction"] = {"status": "asserted", "evidence_for_direction": "experimental"}
        # evidential basis
        low = self.alltext.lower()
        if claim.design == "exp":
            et = "randomized_experiment" if re.search(r"\brandom", low) else "quasi_experiment"
        elif claim.design == "obs":
            et = "observational_longitudinal" if re.search(r"years?|monthly|repeated", self.context.lower()) else "observational_cross_sectional"
        elif claim.design == "rev":
            et = "meta_analysis" if "meta-analys" in low else "systematic_review"
        elif claim.design == "mod":
            et = "modeling_simulation"
        else:
            et = "expert_judgment"
        if k.get("med"):
            obj = "both"
        elif claim.design == "jud" and "mechanistic" in e["philosophical_accounts"]:
            obj = "mechanism"
        else:
            obj = "correlation"
        e["evidential_basis"] = {"evidence_types": [et], "evidence_objects": [obj]}
        # scope
        if k.get("scope") == "c" or _CONTINGENT.search(text):
            e["scope"] = "contingent"
        elif _PROTO.search(text):
            e["scope"] = "prototypical"
        else:
            e["scope"] = "assertional"
        if k.get("dose"):
            d = self.parse_dose(k["dose"])
            if d:
                e["dose"] = d
        if k.get("lvl", "").lower() in DOSE_LEVELS:
            e["dose_level"] = k["lvl"].lower()
        if k.get("vs"):
            vs = k["vs"]
            ctype = ("untreated_control" if _CTRL.search(vs) else "alternative_dose_level" if _DOSE_WORDS.search(vs)
                     else "alternative_treatment")
            e["comparator"] = [{"status": "explicitly_asserted", "comparator_type": ctype, "comparator_description": vs}]
        seasons = [s.strip().lower() for s in re.split(r"[,/ ]+", k.get("season", "")) if s.strip().lower() in SEASONS]
        if seasons:
            e["temporal_extent"] = {"observation_seasons": list(dict.fromkeys(seasons))}
        return e

    # ------------------------------------------------------------------ claims
    def add_edge(self, subject: str, obj: str, claim: Claim, spans: List[dict], extra: dict, path: bool = False) -> str:
        self.n_edge += 1
        eid = f"{self.slug}-e{self.n_edge}"
        text = " ".join((self.sent[n].get("clean") or "") for n in claim.sentences if n in self.sent)
        comp = " ".join((self.sent[n].get("compressed") or "") for n in claim.sentences if n in self.sent)
        fields = self.edge_fields(claim, spans, text, comp)
        if path:
            for k in ("dose", "dose_level", "comparator"):
                fields.pop(k, None)
        edge = {"id": eid, "source_document": self.slug, "subject": subject, "predicate": PRED_ENUM[claim.predicate],
                "object": obj}
        edge.update(fields)
        edge.update(extra)
        edge["source_spans"] = spans
        self.out.edges.append(edge)
        return eid

    def expand(self, claims: List[Claim]) -> Expanded:
        for claim in claims:
            spans = self.spans(claim.sentences)
            if not spans:
                self.out.stats["no_spans"] = self.out.stats.get("no_spans", 0) + 1
                continue
            stage = claim.keys.get("stage", "").lower() or None
            subj = self.node(claim.cause, None, spans)
            med_var = parse_var(claim.keys["med"]) if claim.keys.get("med") else None
            for eff in claim.effects:
                obj = self.node(eff, stage, spans, null_effect=(claim.kind == "N"))
                extra: dict = {}
                if med_var is not None:
                    mid = self.node(med_var, None, spans)
                    extra["mediation"] = {"status": "explicitly_asserted", "mediator_node_ids": [mid]}
                self.add_edge(subj, obj, claim, spans, extra)
                if med_var is not None:
                    pc = Claim(claim.kind, claim.sentences, claim.cause, claim.predicate, [eff], claim.language, claim.design,
                               {k: v for k, v in claim.keys.items() if k not in ("med", "dose", "lvl", "vs")}, claim.raw)
                    self.add_edge(subj, mid, pc, spans, {}, path=True)
                    self.add_edge(mid, obj, pc, spans, {}, path=True)
        return self.out


_ACTION_NOUN = re.compile(r"^(establishment|planting|transplant\w*|release|introduction|reintroduction|restoration|removal|"
                          r"construction|application|harvest\w*|closure|cessation|burning|seeding|mowing|grazing|thinning|"
                          r"installation|recovery|treatment)\b", re.I)
_UNDO = re.compile(r"\b(closure|removal|cessation|abandonment|end)\b", re.I)
_CATEGORY = re.compile(r"\b(type|class|category|group|status|use|stage|zone)$", re.I)
_ADJ_ENTITY = re.compile(r"^(herbaceous|woody|native|exotic|non-?native|invasive|natural|aquatic|terrestrial|total|planted|"
                         r"understou?ry|overstou?ry)$", re.I)


def compose_name(change: Optional[str], prop: Optional[str], text: str) -> str:
    return _tidy_name(_compose_name(change, prop, text))


def _tidy_name(n: str) -> str:
    n = re.sub(r" of (.+) of \1$", r" of \1", n)
    n = re.sub(r"^(Presence|Occurrence) of (presence|occurrence) of ", r"\1 of ", n, flags=re.I)
    return n


def _compose_name(change: Optional[str], prop: Optional[str], text: str) -> str:
    """Readable node name from (change, property, thing).  Avoids the template artefacts seen in the full run:
    'Presence of establishment of X' (an action named as presence), 'Removal of smelter closure' (double action),
    'establishment of X of X' (taxon repeated), 'Natural of ecotone type' (a value in the property slot) and
    'species richness of herbaceous' (an adjective as the thing)."""
    p = (prop or "").strip()
    t = re.sub(r" of (.+) of \1$", r" of \1", (text or "").strip())     # 'establishment of X of X' -> 'establishment of X'
    t = re.sub(r"^(presence|occurrence) of ", "", t, flags=re.I) if change in ("pres", "occ") else t
    if p and t and (t.lower() in p.lower()):            # property already names the thing
        core = p
    elif p and _CATEGORY.search(t) and len(p.split()) <= 3:   # 'natural' + 'ecotone type' -> 'natural ecotone type'
        core = f"{p} {t}"
    elif p and _ADJ_ENTITY.match(t):                  # 'species richness' + 'herbaceous' -> 'herbaceous species richness'
        core = f"{t} {p}"
    else:
        core = f"{p} of {t}" if p else t
    if change in _ADJ:
        return f"{_ADJ[change]} {core}"
    if change in _NOUN:
        if _ACTION_NOUN.match(core):
            if change == "rem" and _UNDO.match(core):  # 'removal' of a 'closure' is the closure itself
                return core
            if change in ("pres", "occ", "intro"):     # 'Presence of establishment of X' -> 'Establishment of X'
                return core
        if change == "rem" and _UNDO.search(core):     # 'Removal of Coniston Smelter closure' -> 'Coniston Smelter closure'
            return core
        return f"{_NOUN[change]} {core}"
    return core


def calibrate_language(lang: str, design: str, text: str) -> str:
    """direct_causal on a hedged sentence (may, might, could, would, appears, seems, suggests) -> uncertain_causal."""
    if lang == "direct_causal" and _HEDGE.search(text or ""):
        return "uncertain_causal"
    return lang


def expand_claims(slug: str, claims: List[Claim], side: dict) -> Expanded:
    return Expander(slug, side).expand(claims)
