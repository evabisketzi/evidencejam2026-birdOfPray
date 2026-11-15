"""Stage 5b (--ontology off|lookup|select, default lookup): ontology IDs for the free-text terms of one paper's nodes.

Takes the LLM step's output for one paper (the nodes after expansion and the guard) and runs the team's grounding module
ontology/ground_terms.py + select_terms.py (see ontology/GROUNDING.md) on it, unchanged; this file only adapts it:

  lookup  ground_terms looks every free-text entity_term / measured_attribute / life_stage_term up in the committed indexes
          (NCBITaxon, ELMO, ENVO, GO, PATO, ChEBI, PO, UBERON) by the field and the node's entity_type, and writes an ID only
          for a unique exact label / exact-synonym match.  No LLM call.
  select  lookup, then the ambiguous / needs_review terms go to select_terms.select_candidates: the model picks a candidate
          NUMBER (one short call per paper, through the pipeline's own Client: same cache, retries, thinking switch, token
          count), never writes an ID.  Decisions on non-taxon terms are remembered across papers in a memo.

Values that already are CURIEs (NCBITaxon IDs from data/ncbitaxon_names.tsv, verified data/terms.tsv rows) are left as they
are: only taxa the TSV missed, and other free text, are looked up.  `fields="entities"` grounds entity_term (taxa included)
and life_stage_term only; measured_attribute stays free text.  A failure inside the stage never costs the paper: its nodes
stay as the guard left them.
"""
from __future__ import annotations

import copy
import logging
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = ROOT / "ontology"
MODES = ("off", "lookup", "select")
FIELD_SETS = ("all", "entities")
_ENTITY_KINDS = ["taxon", "environmental_variable", "composite_variable", "environmental_process", "management_intervention",
                 "untyped", "life_stage"]
SELECT_MAX_TOKENS = 200          # select_terms asks about at most 20 terms per call and needs ~8 tokens per answer
REPORT_CANDIDATES = 3            # candidates kept per term in ontology_report.json
# Never grounded, whatever matches: words too generic to carry the meaning (from camo_pipeline/ontology.py BLOCKED; e.g.
# 'quality' is an exact synonym of PATO's root term 'characteristic'), and the loose ELMO exact synonyms listed under "Known
# limitations" in ontology/GROUNDING.md (the process 'competition' would become the variable 'competition intensity').
BLOCKED = {"quality", "characteristic", "characteristics", "number", "rate", "response", "increased", "decreased", "present",
           "absent", "normal", "abnormal", "change", "effect", "value", "level", "competition", "succession"}


def _import_ontology():
    if str(ONTOLOGY_DIR) not in sys.path:
        sys.path.insert(0, str(ONTOLOGY_DIR))
    import ground_terms   # noqa: WPS433  (the team module lives in ontology/, not in a package)
    import select_terms
    return ground_terms, select_terms


def _report_row(g: dict, chosen: Optional[str]) -> dict:
    return {"kind": g["kind"], "query": g["query"], "status": g["status"], "id": chosen,
            "nodes": len({tuple(loc["path"][:2]) for loc in g.get("locations", [])}),
            "candidates": [{"id": c["curie"], "label": c.get("label"), "match": c.get("match_type"), "score": c.get("score")}
                           for c in (g.get("candidates") or [])[:REPORT_CANDIDATES]]}


class OntologyStage:
    def __init__(self, mode: str = "lookup", fields: str = "all", client=None, memo_path: Optional[Path] = None):
        if mode not in MODES or mode == "off":
            raise ValueError(f"mode must be lookup or select, not {mode!r}")
        if fields not in FIELD_SETS:
            raise ValueError(f"fields must be one of {FIELD_SETS}, not {fields!r}")
        self.gt, self.st = _import_ontology()
        self.mode, self.fields = mode, fields
        self.registry = self.gt.Registry(self.gt.load_config(), self.gt.Prefixes(self.gt.CAMO_PREFIXES))
        self.kinds = _ENTITY_KINDS + (["measured_attribute"] if fields == "all" else [])
        for k in self.kinds:                                   # load every index now: read-only afterwards, shared by threads
            self.registry.for_kind(k)
        self.client = client
        self.memo_path = Path(memo_path) if memo_path else Path(self.st.DEFAULT_MEMO)
        self.memo = self.st.load_memo(self.memo_path) if mode == "select" else {}
        self._memo_at_start = dict(self.memo)
        self._lock = threading.Lock()
        self.totals: Counter = Counter()

    # --- the model, through the pipeline's Client (cache, retries, thinking off, token accounting) -------------------------
    def _llm(self, system: str, user: str, max_tokens: int) -> Tuple[str, dict]:
        r = self.client.complete(system, user, "ontology")
        return r.text, {"prompt_tokens": 0 if r.cached else r.prompt_tokens,
                        "completion_tokens": 0 if r.cached else r.completion_tokens, "finish_reason": None}

    def ground(self, slug: str, nodes: Dict[str, dict]) -> Tuple[Dict[str, dict], Counter, Dict[str, int], List[dict]]:
        """-> (nodes with IDs written in, stats, tokens {prompt_tokens, completion_tokens}, report rows).
        Any error: the nodes unchanged, stat 'ontology: error'."""
        stats: Counter = Counter()
        tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        if not nodes:
            return nodes, stats, tokens, []
        try:
            doc = {"nodes": [copy.deepcopy(n) for n in nodes.values()]}
            report = self.gt.ground_graph(doc, self.registry, kinds=self.kinds, verbose=False)
            for g in report["terms"]:
                if g["query"].strip().lower() in BLOCKED:
                    g.update(status="blocked", selected=None, candidates=[])
            selections: dict = {}
            if self.mode == "select" and self.client is not None:
                with self._lock:
                    memo = dict(self.memo)                     # own copy: the model calls of different papers run in parallel
                before = dict(memo)
                selections, st = self.st.select_candidates(report, self._llm, memo, log=lambda m: log.info("%s: %s", slug, m))
                with self._lock:
                    self.memo.update({k: v for k, v in memo.items() if k not in before})
                tokens = {"prompt_tokens": st["prompt_tokens"], "completion_tokens": st["completion_tokens"]}
                stats.update({f"ontology select: {k}": v for k, v in st.items() if k not in ("prompt_tokens", "completion_tokens") and v})
            grounded = self.gt.apply_groundings(doc, report, selections)
            rows = []
            for g in report["terms"]:
                chosen = g["selected"] if g["status"] == "resolved" else selections.get(g.get("key"))
                stats[f"ontology {g['kind']}: {'grounded' if chosen else g['status']}"] += 1
                rows.append(_report_row(g, chosen))
            out = {n["id"]: n for n in grounded["nodes"]}
        except Exception as e:  # noqa: BLE001 - grounding is an extra: never lose the paper over it
            log.warning("%s: ontology stage failed, nodes kept as they were: %s: %s", slug, type(e).__name__, e)
            stats = Counter({"ontology: error": 1})
            return nodes, stats, {"prompt_tokens": 0, "completion_tokens": 0}, []
        with self._lock:
            self.totals.update(stats)
        return out, stats, tokens, rows

    def close(self) -> None:
        """Save the selection memo, only when this run added decisions (no empty or unchanged file is written)."""
        if self.mode == "select":
            with self._lock:
                if self.memo != self._memo_at_start:
                    self.st.save_memo(self.memo, self.memo_path)

    def summary(self) -> str:
        grounded = sum(v for k, v in self.totals.items() if k.endswith(": grounded"))
        terms = sum(v for k, v in self.totals.items() if k.startswith("ontology ") and "select" not in k and k != "ontology: error")
        errors = self.totals.get("ontology: error", 0)
        return (f"ontology ({self.mode}, {self.fields}): {grounded} of {terms} distinct free-text terms per paper got an ID"
                + (f"; stage failed on {errors} paper(s), kept ungrounded" if errors else ""))


def stage_from_args(mode: str, fields: str = "all", base_cfg=None, Client=None) -> Optional[OntologyStage]:
    """None for mode off.  For select, a Client of its own: small output cap and its own cache entries."""
    if mode == "off":
        return None
    client = None
    if mode == "select":
        cfg = copy.copy(base_cfg)
        cfg.max_tokens = SELECT_MAX_TOKENS
        cfg.cache_salt = "ontology-select-1"
        client = Client(cfg)
    return OntologyStage(mode, fields, client)


def regrounded(nodes: Dict[str, dict], edges: List[dict], slug: str, stage: OntologyStage, guard_paper
               ) -> Tuple[Dict[str, dict], List[dict], Counter, Dict[str, int], List[dict]]:
    """Ground, then validate again with the guard: a bad ID costs that one field, never the edge or the paper.
    -> (nodes, edges, stats, tokens, report rows)."""
    gnodes, stats, tokens, rows = stage.ground(slug, nodes)
    if gnodes is nodes:                                        # nothing to ground, or the stage failed: already guarded
        return nodes, edges, stats, tokens, rows
    n2, e2, gstats = guard_paper(slug, gnodes, edges)
    stats.update({k: v for k, v in gstats.items() if k.startswith(("field", "dropped edge", "repair: undeclared"))})
    return n2, e2, stats, tokens, rows
