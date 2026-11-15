"""Code-only options ported from camo_pipeline (pipeline/features.py): --fit-attributes, --double-negative, --provenance."""
import json
import re
from pathlib import Path

import pytest

from pipeline.expand import expand_claims
from pipeline.features import OFF, Features, add_provenance, agent_id, fit_attribute, repair_double_negative, variable_key
from pipeline.guard import guard_paper, validate_graph, wrapper_graph
from pipeline.parse import parse_text
from tests.test_pipeline import EXAMPLES, sidecar

FIT = Features(fit_attributes=True)


def _expand(lines, features=OFF):
    claims, bad = parse_text("\n".join(lines))
    assert not bad
    return expand_claims("DOC", claims, sidecar(), features)


@pytest.mark.parametrize("prop,change,stage,expected", [
    ("seedling number", None, None, ("number of individuals", None, "seedling", None)),
    ("rosette number", None, None, ("number of individuals", None, "juvenile", "rosette")),
    ("seedlings", None, None, ("number of individuals", None, "seedling", None)),
    ("seedling height", None, None, ("height", None, "seedling", None)),
    ("increased cover", None, None, ("cover", "+", None, None)),
    ("reduced seedling survival", None, None, ("survival", "-", "seedling", None)),
    ("seedling height", None, "adult", ("height", None, "adult", None)),          # a stage= key wins
    ("cover", "+", None, ("cover", "+", None, None)),                            # nothing to fit: unchanged
    ("initial planting density", None, None, ("initial planting density", None, None, None)),
    (None, "-", None, (None, "-", None, None)),
])
def test_fit_attribute(prop, change, stage, expected):
    assert fit_attribute(prop, change, stage) == expected


def test_fit_attributes_makes_stage_wordings_one_variable():
    lines = ["F|12|T1/density/+/tax|c|T2/seedling number/-|D|exp",
             "F|13|T1/density/+/tax|c|T2/number of individuals/-|D|exp|stage=seedling"]
    off, on = _expand(lines), _expand(lines, FIT)
    assert len({e["object"] for e in off.edges}) == 2
    assert len({e["object"] for e in on.edges}) == 1
    node = on.nodes[on.edges[0]["object"]]
    # 'number of individuals' is a verified row of data/terms.tsv, so the fitted attribute also gets its ID
    assert node["measured_attribute"] == "PATO:0000070" and node["life_stage"] == "germinant_or_seedling"


def test_fit_attributes_writes_life_stage_term_and_still_validates():
    exp = _expand(["F|5|T1/density/+/tax|c|T2/rosette number/-|D|exp"], FIT)
    nodes, edges, _ = guard_paper("DOC", exp.nodes, exp.edges)
    obj = nodes[edges[0]["object"]]
    assert obj["life_stage"] == "juvenile" and obj["life_stage_term"] == "rosette"
    assert validate_graph(wrapper_graph(list(nodes.values()), edges)) is None


def test_default_features_change_nothing_on_the_prompt_examples():
    a, b = _expand(EXAMPLES), _expand(EXAMPLES, OFF)
    assert a.nodes == b.nodes and a.edges == b.edges


def test_double_negative():
    nodes = {"s": {"id": "s"}, "o": {"id": "o", "state_or_change_qualifier": "decreased"}, "u": {"id": "u"}}
    e = {"predicate": "prevents", "object": "o"}
    assert repair_double_negative(e, nodes) == "prevents+decreased->causes" and e["predicate"] == "causes"
    for e in ({"predicate": "prevents", "object": "u"}, {"predicate": "causes", "object": "o"},
              {"predicate": "prevents", "object": "o", "negated": True}):
        before = dict(e)
        assert repair_double_negative(e, nodes) is None and e == before


def test_double_negative_through_the_guard():
    exp = _expand(["F|41|planting(T1)/occ/mgmt|p|invasion(T2)/spread/-|U|jud"])
    _, edges, _ = guard_paper("DOC", exp.nodes, [dict(e) for e in exp.edges])
    assert edges[0]["predicate"] == "prevents"                                # off by default
    _, edges, stats = guard_paper("DOC", exp.nodes, [dict(e) for e in exp.edges], Features(double_negative=True))
    assert edges[0]["predicate"] == "causes" and stats["repair: prevents+decreased->causes"] == 1


def test_provenance_matches_the_schema():
    assert agent_id("Qwen3.8-27B") == "camo_agent:Qwen3.8-27B"
    assert re.fullmatch(r"camo_agent:[A-Za-z0-9._-]+", agent_id("org/model name:v1"))
    exp = _expand(EXAMPLES)
    nodes, edges, _ = guard_paper("DOC", exp.nodes, exp.edges)
    add_provenance(nodes, edges, "Qwen3.8-27B", "2026-11-15T12:00:00Z")
    assert all(n["annotator"] == "camo_agent:Qwen3.8-27B" and n["variable_key"] for n in nodes.values())
    assert all(e["annotation_timestamp"] == "2026-11-15T12:00:00Z" for e in edges)
    assert validate_graph(wrapper_graph(list(nodes.values()), edges)) is None


def test_variable_key_ignores_case_and_punctuation_but_keeps_curies():
    a = {"entity_term": "Soil  Moisture", "measured_attribute": "Cover!", "applied_to": [{"entity_term": "NCBITaxon:3472"}]}
    b = {"entity_term": "soil moisture", "measured_attribute": "cover", "applied_to": [{"entity_term": "NCBITaxon:3472"}]}
    assert variable_key(a) == variable_key(b) == "soil moisture|cover|NCBITaxon:3472"


def test_from_names():
    assert Features.from_names("fit-attributes, provenance") == Features(fit_attributes=True, provenance=True)
    assert Features.from_names("") == OFF
    with pytest.raises(ValueError):
        Features.from_names("fit-atributes")


def test_whole_run_with_every_option_on_validates(monkeypatch, tmp_path):
    from tests.test_ontology_stage import _patch
    import pipeline.ontology_stage as osm
    monkeypatch.setattr(osm.OntologyStage, "close", lambda self: None)
    m = _patch(monkeypatch)
    root = Path(__file__).resolve().parent.parent
    rc = m.run(root / "corpus", tmp_path / "o", docs=["YKQQZV93"], concurrency=1, use_cache=False, ontology="select",
               features=Features(True, True, True))
    assert rc == 0                                                            # JSON Schema + linkml (when installed) pass
    g = json.loads((tmp_path / "o" / "camo_graph.json").read_text(encoding="utf-8"))
    assert all(e["annotator"].startswith("camo_agent:") for e in g["edges"])
    log = json.loads((tmp_path / "o" / "run_log.json").read_text(encoding="utf-8"))
    assert log["features"] == ["double_negative", "fit_attributes", "provenance"]
