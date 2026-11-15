#!/usr/bin/env python3
"""
Tests for the grounding pipeline (ground_terms.py + select_terms.py).

  python tests/test_grounding.py              # unit tests + gold check (deterministic step)
  python tests/test_grounding.py --with-llm   # also run select_terms on the pending gold
                                              # terms (needs BRINE_URL/MODEL/API_KEY)

Also runs under pytest. The gold check reports precision and recall of the auto-resolved
CURIEs (and, with --with-llm, of the LLM's selections) against tests/grounding_gold.yaml.
Taxon entries are skipped while ontology_index/ncbitaxon.json.gz has not been built.
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ground_terms import (CAMO_PREFIXES, INDEX_DIR, Prefixes, Registry, apply_groundings,  # noqa: E402
                          fix_units, ground_graph, load_config)
from select_terms import parse_reply, select_candidates  # noqa: E402

GOLD = ROOT / "tests" / "grounding_gold.yaml"
_REGISTRY = None


def registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry(load_config(), Prefixes(CAMO_PREFIXES))
    return _REGISTRY


# ---------------------------------------------------------------------------
# unit tests
# ---------------------------------------------------------------------------

def test_parse_reply() -> None:
    expected = {"T1": 2, "T2": 3}
    assert parse_reply('{"T1": 2, "T2": 0}', expected) == {"T1": 2, "T2": 0}
    assert parse_reply('<think>hmm {"T1": 1}</think>\n```json\n{"T1": 1, "T2": "3"}\n```', expected) == {"T1": 1, "T2": 3}
    assert parse_reply('{"T1": 7, "T9": 1, "T2": -1}', expected) == {}            # out of range / unknown id
    assert parse_reply("T1: 2, T2: 1", expected) == {"T1": 2, "T2": 1}             # not JSON
    assert parse_reply("no idea", expected) == {}


def test_fix_units() -> None:
    doc = {"a": {"numeric_value": 5, "unit": "ramets/m2"}, "b": [{"unit": "unit:M2"}],
           "c": {"unit": "deer/km2", "unit_text": "deer per km2"}}
    assert fix_units(doc) == 2
    assert doc["a"] == {"numeric_value": 5, "unit_text": "ramets/m2"}
    assert doc["b"][0] == {"unit": "unit:M2"}
    assert doc["c"] == {"unit_text": "deer per km2"}


def test_select_and_apply_with_fake_llm() -> None:
    doc = {"nodes": [
        {"name": "Increased aboveground plant biomass", "entity_type": "environmental_variable",
         "entity_term": "aboveground plant biomass", "measured_attribute": "height",
         "dose": {"numeric_value": 3, "unit": "ramets/m2"}},
        {"name": "Soil pH", "entity_type": "environmental_variable", "entity_term": "soil pH"},
    ]}
    report = ground_graph(doc, registry(), verbose=False)
    by_query = {g["query"]: g for g in report["terms"]}
    assert by_query["soil pH"]["status"] == "resolved"
    pending = by_query["aboveground plant biomass"]
    assert pending["status"] == "needs_review"
    pick = next(i for i, c in enumerate(pending["candidates"], 1) if c["curie"] == "elmo:3622501")

    calls = []

    def fake_llm(system: str, user: str, max_tokens: int):
        calls.append(user)
        return f'{{"T1": {pick}}}', {"prompt_tokens": 100, "completion_tokens": 5}

    memo: dict = {}
    selections, stats = select_candidates(report, fake_llm, memo, log=lambda m: None)
    assert stats["calls"] == 1 and stats["chosen"] == 1, stats
    assert '"aboveground plant biomass"' in calls[0] and "Increased aboveground plant biomass" in calls[0]
    grounded = apply_groundings(doc, report, selections)
    assert grounded["nodes"][0]["entity_term"] == "elmo:3622501"
    assert grounded["nodes"][0]["measured_attribute"] == "PATO:0000119"
    assert grounded["nodes"][0]["dose"] == {"numeric_value": 3, "unit_text": "ramets/m2"}
    assert grounded["nodes"][1]["entity_term"] == "elmo:3622101"
    assert doc["nodes"][0]["entity_term"] == "aboveground plant biomass"           # input untouched

    # second article with the same term: answered from the memo, no call
    calls.clear()
    selections2, stats2 = select_candidates(copy.deepcopy(report), fake_llm, memo, log=lambda m: None)
    assert not calls and stats2["memo_hits"] == 1 and selections2 == selections


def test_existing_curies_checked() -> None:
    doc = {"nodes": [{"name": "Leaf senescence", "entity_type": "environmental_process", "entity_term": "GO:0010150"},
                     {"name": "x", "entity_type": "environmental_variable", "entity_term": "PATO:9999999"},
                     {"name": "y", "entity_type": "taxon", "entity_term": "http://aims.fao.org/aos/agrovoc/c_1"}]}
    report = ground_graph(doc, registry(), verbose=False)
    status = {c["curie"]: c["status"] for c in report["existing_curies"]}
    assert status["GO:0010150"] == "ok"
    assert status["PATO:9999999"].startswith("not_found")
    assert not report["terms"]                                                   # the IRI is left alone


def test_demo_graph() -> None:
    """tests/demo_graph.yaml, the walkthrough in GROUNDING.md."""
    from ground_terms import load_doc
    doc = load_doc(str(ROOT / "tests" / "demo_graph.yaml"))
    report = ground_graph(doc, registry(), verbose=False)
    out = apply_groundings(doc, report)
    nodes = {n["id"].split(":")[1]: n for n in out["nodes"]}
    assert nodes["demo_transplanting"]["entity_term"] == "elmo:3621055"           # transplanting process
    assert nodes["demo_alliaria_seedlings"]["life_stage_term"] == "PO:0007131"    # seedling development stage
    assert nodes["demo_alliaria_height"]["measured_attribute"] == "PATO:0000119"  # height
    assert nodes["demo_alliaria_height"]["life_stage_term"] == "PO:0007616"       # flowering stage
    assert nodes["demo_light"]["entity_term"] == "elmo:3622714"                   # light availability
    assert out["edges"][0]["dose"]["unit_text"] == "ramets/m2" and "unit" not in out["edges"][0]["dose"]
    if (INDEX_DIR / "ncbitaxon.json.gz").exists():
        assert nodes["demo_alliaria_seedlings"]["entity_term"] == "NCBITaxon:126270"
        assert nodes["demo_alliaria_height"]["entity_term"] == "NCBITaxon:126270"   # "A. petiolata", expanded


# ---------------------------------------------------------------------------
# gold check
# ---------------------------------------------------------------------------

def gold_doc(entries: list[dict]) -> dict:
    nodes = []
    for e in entries:
        if e["kind"] == "measured_attribute":
            nodes.append({"measured_attribute": e["text"]})
        elif e["kind"] == "life_stage":
            nodes.append({"life_stage_term": e["text"]})
        elif e["kind"] == "unit":
            nodes.append({"quantity": {"numeric_value": 1, "unit": e["text"]}})
        else:
            nodes.append({"entity_type": e["kind"], "entity_term": e["text"]})
    return {"nodes": nodes}


def gold_check(with_llm: bool = False) -> dict:
    entries = yaml.safe_load(GOLD.read_text(encoding="utf-8"))
    if not (INDEX_DIR / "ncbitaxon.json.gz").exists():
        skipped = [e for e in entries if e["kind"] == "taxon"]
        entries = [e for e in entries if e["kind"] != "taxon"]
        print(f"(skipping {len(skipped)} taxon entries: ncbitaxon index not built)")
    report = ground_graph(gold_doc(entries), registry(), verbose=False)
    group_of = {(g["kind"], m): g for g in report["terms"] for m in g["mentions"]}
    selections: dict = {}
    if with_llm:
        from select_terms import brine_llm
        selections, stats = select_candidates(report, brine_llm, memo={})
        print("LLM stats:", stats)

    def score(predicted: dict) -> dict:
        tp = sum(1 for e in entries if predicted.get(e["text"]) and predicted[e["text"]] == e["expect"])
        made = sum(1 for e in entries if predicted.get(e["text"]))
        wrong = [(e["text"], predicted[e["text"]], e["expect"]) for e in entries
                 if predicted.get(e["text"]) and predicted[e["text"]] != e["expect"]]
        positives = sum(1 for e in entries if e["expect"])
        return {"assigned": made, "correct": tp, "precision": round(tp / made, 3) if made else None,
                "recall": round(tp / positives, 3) if positives else None, "wrong": wrong}

    auto = {e["text"]: group_of[(e["kind"], e["text"])]["selected"] for e in entries
            if group_of.get((e["kind"], e["text"])) and group_of[(e["kind"], e["text"])]["status"] == "resolved"}
    result = {"entries": len(entries), "auto": score(auto)}
    if with_llm:
        combined = dict(auto)
        for e in entries:
            g = group_of.get((e["kind"], e["text"]))
            if g and g["key"] in selections:
                combined[e["text"]] = selections[g["key"]]
        result["auto+llm"] = score(combined)
    return result


def test_gold_precision() -> None:
    result = gold_check()
    assert result["auto"]["precision"] is not None and result["auto"]["precision"] >= 0.9, result


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn) and name != "test_gold_precision":
            fn()
            print(f"ok  {name}")
    res = gold_check(with_llm="--with-llm" in sys.argv and bool(os.environ.get("BRINE_URL")))
    print("gold:", yaml.safe_dump(res, sort_keys=False, allow_unicode=True))
    assert res["auto"]["precision"] >= 0.9, "auto-resolved precision below 0.9"
    print("ok  gold precision >= 0.9")
