"""--study: study-level facts for source_documents (pipeline/study.py)."""
import json
from pathlib import Path

import pytest

from pipeline.extract import Client
from pipeline.guard import merge, validate_graph
from pipeline.study import apply_design, evidence_types, parse_reply, study_facts

ROOT = Path(__file__).resolve().parent.parent


def test_parse_reply_keeps_only_checked_values():
    r = parse_reply('{"design":"randomized_experiment","country":"Canada","region":"Ontario","start":"2001","end":"2003","months":36}')
    assert r == {"study_design": "randomized_experiment", "study_country": "Canada", "study_state_or_province": "Ontario",
                 "study_period_start": "2001", "study_period_end": "2003", "study_duration_months": 36.0}
    assert parse_reply('{"design":"BACI","start":"spring 2001","end":"1999","months":-3,"country":"unknown"}') == {
        "study_design": "quasi_experiment", "study_period_end": "1999"}       # synonym kept; bad start, months, country dropped
    assert parse_reply('```json\n{"design":"made_up","start":"2004-06"}\n```') == {"study_period_start": "2004-06"}
    assert parse_reply("not json at all") == {} and parse_reply('["a"]') == {}
    assert parse_reply('{"start":"2005","end":"2001"}') == {"study_period_start": "2005"}   # end before start: dropped


def test_enum_comes_from_the_schema():
    assert "randomized_experiment" in evidence_types() and "observational_longitudinal" in evidence_types()


def test_apply_design_only_within_the_same_family():
    edges = [{"id": "a", "evidential_basis": {"evidence_types": ["quasi_experiment"]}},
             {"id": "b", "evidential_basis": {"evidence_types": ["observational_cross_sectional"]}},
             {"id": "c", "evidential_basis": {"evidence_types": ["expert_judgment"]}},
             {"id": "d"}]
    assert apply_design(edges, "randomized_experiment") == 1
    assert [e.get("evidential_basis", {}).get("evidence_types") for e in edges] == [
        ["randomized_experiment"], ["observational_cross_sectional"], ["expert_judgment"], None]
    assert apply_design(edges, None) == 0


def test_no_context_or_a_failed_call_gives_no_facts():
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("down")
    assert study_facts(Boom(), "t", "") == ({}, {"prompt_tokens": 0, "completion_tokens": 0})
    assert study_facts(Boom(), "t", "some context")[0] == {}


def test_merge_puts_the_facts_on_source_documents():
    rows = [{"slug": "A", "doi": "10.1/x", "title": "T"}, {"slug": "B", "doi": "", "title": "U"}]
    e = {"id": "A-e1", "source_document": "A", "subject": "n1", "predicate": "causes", "object": "n2",
         "causal_language": "direct_causal", "original_sentence": "s", "philosophical_accounts": ["regularity"]}
    nodes = {i: {"id": i, "name": i, "entity_type": "environmental_variable", "entity_term": i} for i in ("n1", "n2")}
    g = merge(rows, {"A": (nodes, [e])}, study={"A": {"study_design": "randomized_experiment", "study_country": "Canada"}})
    a, b = g["source_documents"]
    assert a["study_design"] == "randomized_experiment" and a["study_country"] == "Canada" and "study_design" not in b
    assert validate_graph(g) is None


def test_whole_run_with_study_validates(monkeypatch, tmp_path):
    import pipeline.main as m
    from tests.test_pipeline import _fake_post_factory
    extraction = _fake_post_factory()

    def post(url, payload):
        if "study-level facts" in payload["messages"][0]["content"]:
            return 200, {"choices": [{"message": {"content": '{"design":"randomized_experiment","country":"Canada","start":"2001"}'}}],
                         "usage": {"prompt_tokens": 120, "completion_tokens": 15}}
        return extraction(url, payload)
    for k, v in (("BRINE_URL", "http://h/v1"), ("BRINE_MODEL", "m"), ("BRINE_API_KEY", "k")):
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(m, "Client", lambda cfg, **k: Client(cfg, sleep=lambda s: None, post=post, **k))
    assert m.run(ROOT / "corpus", tmp_path / "o", docs=["YKQQZV93"], concurrency=1, use_cache=False, study=True) == 0
    g = json.loads((tmp_path / "o" / "camo_graph.json").read_text(encoding="utf-8"))
    doc = next(d for d in g["source_documents"] if d["document_id"] == "YKQQZV93")
    assert doc["study_design"] == "randomized_experiment" and doc["study_country"] == "Canada" and doc["study_period_start"] == "2001"
    assert {tuple(e["evidential_basis"]["evidence_types"]) for e in g["edges"]} == {("randomized_experiment",)}
    log = json.loads((tmp_path / "o" / "run_log.json").read_text(encoding="utf-8"))
    assert log["study"] is True and log["papers"][0]["study"]["study_country"] == "Canada"
