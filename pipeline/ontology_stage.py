"""Stage 5b (--ontology lookup|select, default off): ontology IDs for the free-text terms of one paper's nodes.

Uses the team's grounding module ontology/ground_terms.py + select_terms.py (branch ontologies_p_script, see
ontology/GROUNDING.md) unchanged; this file only adapts it to the pipeline:

  lookup  ground_terms looks every free-text entity_term / measured_attribute / life_stage_term up in the committed indexes
          (ELMO, ENVO, GO, PATO, ChEBI, PO, UBERON) by the field and the node's entity_type, and writes an ID only for a
          unique exact label / exact-synonym match.  No LLM call.
  select  lookup, then the ambiguous / needs_review terms go to select_terms.select_candidates: the model picks a candidate
          NUMBER (one short call per paper, through the pipeline's own Client: same cache, retries, thinking switch, token
          count), never writes an ID.  Decisions on non-taxon terms are remembered across papers in a memo.

Taxa are not touched: pipeline/grounding.py already gives NCBITaxon IDs from data/ncbitaxon_names.tsv, and no NCBITaxon
index is committed.  Values that already are CURIEs (verified data/terms.tsv rows, taxa) are left as they are.
`fields="entities"` grounds entity_term and life_stage_term only (measured_attribute stays free text).
"""
from __future__ import annotations

import copy
import json
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
_ENTITY_KINDS = ["environmental_variable", "composite_variable", "environmental_process", "management_intervention",
                 "untyped", "life_stage"]
SELECT_MAX_TOKENS = 200          # select_terms asks about at most 20 terms per call and needs ~8 tokens per answer
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
        for k in self.kinds:                                   # load the indexes now, not inside the first paper
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

    def ground(self, slug: str, nodes: Dict[str, dict]) -> Tuple[Dict[str, dict], Counter, Dict[str, int]]:
        """-> (nodes with IDs written in, stats, tokens {prompt_tokens, completion_tokens})."""
        stats: Counter = Counter()
        tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        if not nodes:
            return nodes, stats, tokens
        doc = {"nodes": [copy.deepcopy(n) for n in nodes.values()]}
        with self._lock:                                       # the registry and the memo are shared by the worker threads
            report = self.gt.ground_graph(doc, self.registry, kinds=self.kinds, verbose=False)
            for g in report["terms"]:
                if g["query"].strip().lower() in BLOCKED:
                    g.update(status="blocked", selected=None, candidates=[])
            selections: dict = {}
            if self.mode == "select" and self.client is not None:
                selections, st = self.st.select_candidates(report, self._llm, self.memo, log=lambda m: log.info("%s: %s", slug, m))
                tokens = {"prompt_tokens": st["prompt_tokens"], "completion_tokens": st["completion_tokens"]}
                stats.update({f"ontology select: {k}": v for k, v in st.items() if k not in ("prompt_tokens", "completion_tokens") and v})
        grounded = self.gt.apply_groundings(doc, report, selections)
        for g in report["terms"]:
            chosen = g["selected"] if g["status"] == "resolved" else selections.get(g.get("key"))
            stats[f"ontology {g['kind']}: {'grounded' if chosen else g['status']}"] += 1
        self.totals.update(stats)
        return {n["id"]: n for n in grounded["nodes"]}, stats, tokens

    def close(self) -> None:
        """Save the selection memo, only when this run added decisions (no empty or unchanged file is written)."""
        if self.mode == "select":
            with self._lock:
                if self.memo != self._memo_at_start:
                    self.st.save_memo(self.memo, self.memo_path)

    def summary(self) -> str:
        grounded = sum(v for k, v in self.totals.items() if k.endswith(": grounded"))
        terms = sum(v for k, v in self.totals.items() if k.startswith("ontology ") and "select" not in k)
        return f"ontology ({self.mode}, {self.fields}): {grounded} of {terms} distinct free-text terms per paper got an ID"


def stage_from_args(mode: str, fields: str, base_cfg=None, Client=None) -> Optional[OntologyStage]:
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


def regrounded(nodes: Dict[str, dict], edges: List[dict], slug: str, stage: OntologyStage, guard_paper) -> Tuple[Dict[str, dict], List[dict], Counter, Dict[str, int]]:
    """Ground, then validate again with the guard: a bad ID costs that one field, never the edge or the paper."""
    gnodes, stats, tokens = stage.ground(slug, nodes)
    n2, e2, gstats = guard_paper(slug, gnodes, edges)
    stats.update({k: v for k, v in gstats.items() if k.startswith(("field", "dropped edge", "repair: undeclared"))})
    return n2, e2, stats, tokens
