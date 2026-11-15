"""Stage 5b (--ontology, default lookup): the team grounding module (ontology/) run on the LLM step's nodes."""
import csv
import json
import re
from pathlib import Path

import pytest

from pipeline.extract import Client, Result
from pipeline.guard import guard_paper, validate_graph, wrapper_graph
from pipeline.ontology_stage import BLOCKED, OntologyStage, regrounded, stage_from_args

ROOT = Path(__file__).resolve().parent.parent


def _node(i, **kw):
    n = {"id": f"node:t_{i}", "name": kw.pop("name", f"Node {i}"), "entity_type": "environmental_variable", "entity_term": "soil"}
    n.update(kw)
    return n


@pytest.fixture(scope="module")
def lookup_all():
    return OntologyStage("lookup", "all")


def test_lookup_grounds_unique_exact_matches_and_leaves_the_rest(lookup_all):
    nodes = {n["id"]: n for n in [
        _node(1, entity_term="soil", measured_attribute="height"),                         # ENVO + PATO
        _node(2, entity_type="taxon", entity_term="NCBITaxon:3472", measured_attribute="cover"),   # taxon ID untouched
        _node(3, entity_term="ENVO:00000002"),                                              # existing CURIE untouched
        _node(4, entity_term="some made-up variable", measured_attribute="quality"),       # no match / blocked
    ]}
    out, stats, tokens, rows = lookup_all.ground("t", nodes)
    assert out["node:t_1"]["entity_term"] == "ENVO:00001998" and out["node:t_1"]["measured_attribute"] == "PATO:0000119"
    assert out["node:t_2"]["entity_term"] == "NCBITaxon:3472" and out["node:t_2"]["measured_attribute"] == "cover"
    assert out["node:t_3"]["entity_term"] == "ENVO:00000002"
    assert out["node:t_4"]["entity_term"] == "some made-up variable" and out["node:t_4"]["measured_attribute"] == "quality"
    assert tokens == {"prompt_tokens": 0, "completion_tokens": 0}
    assert nodes["node:t_1"]["entity_term"] == "soil"                     # the input is not modified
    assert stats["ontology measured_attribute: blocked"] == 1
    soil = next(r for r in rows if r["query"] == "soil")
    assert soil["status"] == "resolved" and soil["id"] == "ENVO:00001998" and soil["candidates"][0]["id"] == "ENVO:00001998"


def test_free_text_taxa_get_ncbitaxon_ids_and_existing_ids_stay(lookup_all):
    nodes = {n["id"]: n for n in [
        _node(1, entity_type="taxon", entity_term="Alliaria petiolata"),                   # the TSV missed it: looked up
        _node(2, entity_type="taxon", entity_term="NCBITaxon:3472"),                       # already an ID: untouched
        _node(3, entity_type="management_intervention", entity_term="mowing",
              applied_to=[{"entity_type": "taxon", "entity_term": "Acer rubrum"}]),
    ]}
    out, stats, _, _ = lookup_all.ground("t", nodes)
    assert out["node:t_1"]["entity_term"] == "NCBITaxon:126270"
    assert out["node:t_2"]["entity_term"] == "NCBITaxon:3472"
    assert out["node:t_3"]["applied_to"] == [{"entity_type": "taxon", "entity_term": "NCBITaxon:45314"}]
    assert stats["ontology taxon: grounded"] == 2


def test_blocked_words_are_never_grounded(lookup_all):
    for w in ("quality", "competition", "succession"):
        assert w in BLOCKED
    out, _, _, _ = lookup_all.ground("t", {"n": _node(1, entity_type="environmental_process", entity_term="competition")})
    assert out["node:t_1"]["entity_term"] == "competition"


def test_entities_mode_keeps_measured_attribute_as_text():
    st = OntologyStage("lookup", "entities")
    out, _, _, _ = st.ground("t", {"n": _node(1, entity_term="soil", measured_attribute="height")})
    assert out["node:t_1"]["entity_term"] == "ENVO:00001998" and out["node:t_1"]["measured_attribute"] == "height"


def test_a_failing_stage_keeps_the_paper_as_the_guard_left_it(lookup_all, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("index broken")
    monkeypatch.setattr(lookup_all.gt, "ground_graph", boom)
    nodes = {"node:t_1": _node(1)}
    out, stats, tokens, rows = lookup_all.ground("t", nodes)
    assert out is nodes and stats == {"ontology: error": 1} and rows == [] and tokens["prompt_tokens"] == 0
    n2, e2, _, _, _ = regrounded(nodes, [], "t", lookup_all, guard_paper)
    assert n2 is nodes


def test_regrounded_output_still_validates_and_keeps_every_edge(lookup_all):
    nodes = {"node:t_1": _node(1, entity_type="management_intervention", entity_term="mowing", state_or_change_qualifier="occurred"),
             "node:t_2": _node(2, entity_term="soil", measured_attribute="temperature", state_or_change_qualifier="increased")}
    edges = [{"id": "t-e1", "source_document": "t", "subject": "node:t_1", "predicate": "causes", "object": "node:t_2",
              "causal_language": "direct_causal", "original_sentence": "Mowing warmed the soil.", "philosophical_accounts": ["interventionist"]}]
    n2, e2, stats, _, rows = regrounded(nodes, edges, "t", lookup_all, guard_paper)
    assert len(e2) == 1 and n2["node:t_1"]["entity_term"].startswith("elmo:")
    assert n2["node:t_2"]["measured_attribute"] == "PATO:0000146"
    assert validate_graph(wrapper_graph(list(n2.values()), e2)) is None
    assert {r["query"] for r in rows} >= {"mowing", "soil", "temperature"}


class _FakeClient:
    """Answers the selection prompt with candidate 1 for every term it is asked about."""
    def __init__(self):
        self.calls = 0

    def complete(self, system, user, label=""):
        self.calls += 1
        ids = re.findall(r"^(T\d+) \[", user, re.M)
        return Result(json.dumps({t: 1 for t in ids}), prompt_tokens=50, completion_tokens=7)


def test_select_lets_the_model_pick_by_number_counts_tokens_and_memoises(tmp_path):
    st = OntologyStage("select", "all", client=_FakeClient(), memo_path=tmp_path / "memo.json")
    nodes = {"n": _node(1, entity_term="soil moisture", measured_attribute="density")}    # fuzzy / related synonym: pending
    out, stats, tokens, _ = st.ground("t", nodes)
    assert out["node:t_1"]["measured_attribute"] == "PATO:0001019" and out["node:t_1"]["entity_term"].startswith("ENVO:")
    assert st.client.calls == 1 and tokens == {"prompt_tokens": 50, "completion_tokens": 7}
    st.close()
    assert json.loads((tmp_path / "memo.json").read_text(encoding="utf-8"))  # decisions remembered for later papers
    st.ground("t", nodes)
    assert st.client.calls == 1                                             # second time: memo, no call


def test_lookup_alone_never_assigns_a_pending_term(lookup_all):
    out, stats, _, _ = lookup_all.ground("t", {"n": _node(1, entity_term="soil moisture", measured_attribute="density")})
    assert out["node:t_1"]["entity_term"] == "soil moisture" and out["node:t_1"]["measured_attribute"] == "density"
    assert stats["ontology measured_attribute: needs_review"] == 1


def test_stage_from_args_off_is_none_and_select_gets_its_own_small_client(tmp_path):
    from pipeline.extract import LLMConfig
    assert stage_from_args("off", "all") is None
    cfg = LLMConfig(url="http://h/v1", model="m", key="k", cache_dir=tmp_path)
    st = stage_from_args("select", "all", cfg, Client)
    assert st.client.cfg.max_tokens == 200 and st.client.cfg.cache_salt == "ontology-select-1"
    assert cfg.max_tokens == 3000 and cfg.cache_salt == ""                  # the extraction config is not changed


def test_cli_default_is_lookup():
    import pipeline.main as m
    import inspect
    assert inspect.signature(m.run).parameters["ontology"].default == "lookup"
    assert inspect.signature(m.run_smoke).parameters["ontology"].default == "lookup"


# --------------------------------------------------------------------------------------- whole run, fake endpoint
def _patch(monkeypatch):
    import pipeline.main as m
    from tests.test_pipeline import _fake_post_factory
    extraction = _fake_post_factory()

    def post(url, payload):
        system, user = payload["messages"][0]["content"], payload["messages"][1]["content"]
        if "ontology terms" in system:                                      # select_terms prompt: candidate 1 for every term
            ids = re.findall(r"^(T\d+) \[", user, re.M)
            return 200, {"choices": [{"message": {"content": json.dumps({t: 1 for t in ids})}}],
                         "usage": {"prompt_tokens": 40, "completion_tokens": 6}}
        return extraction(url, payload)
    for k, v in (("BRINE_URL", "http://h/v1"), ("BRINE_MODEL", "m"), ("BRINE_API_KEY", "k")):
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(m, "Client", lambda cfg, **k: Client(cfg, sleep=lambda s: None, post=post, **k))
    return m


@pytest.mark.parametrize("mode", ["lookup", "select"])
def test_run_with_ontology_validates_and_changes_only_grounded_fields(monkeypatch, tmp_path, mode):
    import pipeline.ontology_stage as osm
    monkeypatch.setattr(osm.OntologyStage, "close", lambda self: None)       # never write the committed memo from a test
    m = _patch(monkeypatch)
    docs = ["YKQQZV93", "4CB9X9XE"]
    assert m.run(ROOT / "corpus", tmp_path / "off", docs=docs, concurrency=1, use_cache=False, ontology="off") == 0
    kw = {} if mode == "lookup" else {"ontology": mode}                     # lookup is the default
    assert m.run(ROOT / "corpus", tmp_path / "on", docs=docs, concurrency=1, use_cache=False, **kw) == 0
    off = json.loads((tmp_path / "off" / "camo_graph.json").read_text(encoding="utf-8"))
    on = json.loads((tmp_path / "on" / "camo_graph.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in off["edges"]] == [e["id"] for e in on["edges"]]
    strip = lambda g: [{k: v for k, v in n.items() if k not in ("entity_term", "measured_attribute", "life_stage_term")} for n in g["nodes"]]
    assert strip(off) == strip(on)                                          # only the grounded fields differ
    attrs = {n.get("measured_attribute") for n in on["nodes"]}
    assert ("PATO:0001019" in attrs) == (mode == "select")                  # 'density' is a related synonym: only the model may pick it
    log = json.loads((tmp_path / "on" / "run_log.json").read_text(encoding="utf-8"))
    assert log["ontology"] == mode and log["ontology_fields"] == "all"
    report = json.loads((tmp_path / "on" / "ontology_report.json").read_text(encoding="utf-8"))
    assert report["mode"] == mode and set(report["papers"]) <= set(docs) and report["papers"]
    assert not (tmp_path / "off" / "ontology_report.json").exists()
    toks = {d: {r["doc"]: int(r["prompt_tokens"]) for r in csv.DictReader(open(tmp_path / d / "tokens.csv", encoding="utf-8"))}
            for d in ("off", "on")}
    extra = sum(toks["on"].values()) - sum(toks["off"].values())
    assert extra == 0 if mode == "lookup" else extra > 0                    # lookup is free; selection tokens are counted per paper
