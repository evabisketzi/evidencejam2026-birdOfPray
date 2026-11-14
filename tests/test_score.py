"""Tests for the dev scorer (dev/score).  Gold files are the real ones in dev/gold/."""
import copy
import random
from pathlib import Path

import pytest
import yaml

from dev.score import cli
from dev.score.load import collapse, load_graph, load_doc_map, merge_loaded
from dev.score.metrics import score, validity_checks
from dev.score.weaken import weaken, wrapper_to_graph

ROOT = Path(__file__).resolve().parent.parent
MURPHY = ROOT / "dev" / "gold" / "murphy2005.yaml"
CB = ROOT / "dev" / "gold" / "4CB9X9XE.camo.yaml"
DOC = "murphy2005"


def gold_murphy():
    g = load_graph(MURPHY, DOC)
    return g.edges_by_doc, g.findings_by_doc


def pred_from(graph: dict, tmp_path, name="pred.yaml"):
    p = Path(tmp_path) / name
    p.write_text(yaml.safe_dump(graph, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return load_graph(p).edges_by_doc


@pytest.fixture(scope="module")
def murphy_graph():
    return wrapper_to_graph(MURPHY, DOC)


def run(graph, tmp_path, threshold=0.6):
    ge, gf = gold_murphy()
    return score(ge, gf, pred_from(graph, tmp_path), None, threshold)


def lv(res, mode, level, key="f1"):
    return res["modes"][mode]["micro"]["levels"][level][key]


# ------------------------------------------------------------------------------------------ gold against itself
@pytest.mark.parametrize("mode", ["raw", "collapse"])
def test_murphy_against_itself_via_a_different_format(murphy_graph, tmp_path, mode):
    res = run(murphy_graph, tmp_path)      # prediction = flattened CausalGraph with different ids
    for level in ("strict", "standard", "loose"):
        assert lv(res, mode, level) == pytest.approx(1.0)
    assert res["modes"][mode]["micro"]["findings"]["recall"] == 1.0


@pytest.mark.parametrize("mode", ["raw", "collapse"])
def test_4cb_against_itself(mode):
    g = load_graph(CB)
    res = score(g.edges_by_doc, {}, g.edges_by_doc)
    for level in ("strict", "standard", "loose"):
        assert lv(res, mode, level) == pytest.approx(1.0)


def test_self_test_command_passes(capsys):
    assert cli.self_test(None) == 0
    assert "self-test passed" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------ perturbations
def test_deleting_10_random_edges_lowers_recall_exactly_and_keeps_precision(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    n = len(g["edges"])
    drop = set(random.Random(3).sample(range(n), 10))
    g["edges"] = [e for i, e in enumerate(g["edges"]) if i not in drop]
    res = run(g, tmp_path)
    for level in ("strict", "standard", "loose"):
        assert lv(res, "raw", level, "precision") == pytest.approx(1.0)
        assert lv(res, "raw", level, "recall") == pytest.approx((n - 10) / n)


def test_flipping_increased_to_decreased_on_5_objects_hurts_standard_and_strict_not_loose(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    nodes = {n["id"]: n for n in g["nodes"]}
    flip = {"increased": "decreased", "decreased": "increased"}
    chosen = [e for e in g["edges"] if not e.get("negated") and e["causal_language"] != "no_relationship"
              and nodes[e["object"]].get("state_or_change_qualifier") in flip][:5]
    assert len(chosen) == 5
    for k, e in enumerate(chosen):          # give each chosen edge its own flipped copy of its object node
        o = copy.deepcopy(nodes[e["object"]])
        o["id"] = f"{o['id']}#flip{k}"
        o["state_or_change_qualifier"] = flip[o["state_or_change_qualifier"]]
        g["nodes"].append(o)
        e["object"] = o["id"]
    res = run(g, tmp_path)
    assert lv(res, "raw", "loose") == pytest.approx(1.0)                       # the right pair of entities is still found
    assert lv(res, "raw", "standard", "recall") == pytest.approx(67 / 72)      # UP vs DOWN is "opposite": fails standard too
    assert lv(res, "raw", "strict", "recall") == pytest.approx(67 / 72)
    assert lv(res, "raw", "strict") < 1.0


def test_flipping_one_null_to_a_positive_edge_breaks_that_match_and_null_recall(murphy_graph, tmp_path):
    base = run(murphy_graph, tmp_path)
    n_null = base["modes"]["raw"]["micro"]["null"]["gold_null"]
    assert n_null == 15
    g = copy.deepcopy(murphy_graph)
    e = next(e for e in g["edges"] if e.get("negated") or e["causal_language"] == "no_relationship")
    e["negated"], e["causal_language"] = False, "direct_causal"
    res = run(g, tmp_path)
    nul = res["modes"]["raw"]["micro"]["null"]
    assert nul["recall"] == pytest.approx((n_null - 1) / n_null)
    assert lv(res, "raw", "standard", "recall") == pytest.approx(71 / 72)
    assert lv(res, "raw", "standard", "precision") == pytest.approx(71 / 72)
    assert lv(res, "raw", "loose", "recall") == pytest.approx(71 / 72)   # null disagreement is a hard 0 at every level


def test_renaming_node_ids_and_changing_entity_types_changes_nothing(murphy_graph, tmp_path):
    base = run(murphy_graph, tmp_path)
    g = copy.deepcopy(murphy_graph)
    m = {n["id"]: f"renamed_{i}" for i, n in enumerate(g["nodes"])}
    types = ["taxon", "management_intervention", "environmental_variable", "environmental_process", "composite_variable"]
    for i, n in enumerate(g["nodes"]):
        n["id"] = m[n["id"]]
        n["entity_type"] = types[(types.index(n["entity_type"]) + 1 + i) % len(types)] if n["entity_type"] in types else "taxon"
    for e in g["edges"]:
        e["subject"], e["object"] = m[e["subject"]], m[e["object"]]
        if e.get("mediation") and e["mediation"].get("mediator_node_ids"):
            e["mediation"]["mediator_node_ids"] = [m[x] for x in e["mediation"]["mediator_node_ids"]]
    res = run(g, tmp_path)
    for mode in ("raw", "collapse"):
        assert res["modes"][mode]["micro"]["levels"] == base["modes"][mode]["micro"]["levels"]
    # entity_type is a diagnostic only: it did change
    assert res["modes"]["raw"]["micro"]["pairs"]["entity_type_agreement"] < 1.0


# ------------------------------------------------------------------------------------------ Murphy quirks
def _wrapper(tmp_path, edge, obj_q="unchanged"):
    d = {"format": "interstitial-camo-graphs/1", "graphs": [{"finding_id": "f1", "sentence": "S.", "graph": {
        "nodes": [{"id": "a", "name": "Driver A", "entity_type": "taxon", "entity_term": "NCBITaxon:3472",
                   "state_or_change_qualifier": "introduced"},
                  {"id": "b", "name": "Response B", "entity_type": "taxon", "entity_term": "NCBITaxon:126270",
                   "state_or_change_qualifier": obj_q}],
        "edges": [dict({"id": "e1", "subject": "a", "object": "b", "predicate": "causes"}, **edge)]}}]}
    p = tmp_path / "w.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    return p


def test_negated_with_uncertain_causal_loads_as_null_with_no_direction_object(tmp_path):
    e = load_graph(_wrapper(tmp_path, {"negated": True, "causal_language": "uncertain_causal"}), "d").edges_by_doc["d"][0]
    assert e.null is True and e.obj.direction == "NONE"


def test_no_relationship_without_negated_is_also_null(tmp_path):
    e = load_graph(_wrapper(tmp_path, {"causal_language": "no_relationship"}, "decreased"), "d").edges_by_doc["d"][0]
    assert e.null is True and e.obj.direction == "NONE"          # forced NONE on a null result's object


def test_positive_edge_keeps_direction_and_unchanged_means_none(tmp_path):
    up = load_graph(_wrapper(tmp_path, {"causal_language": "direct_causal"}, "decreased"), "d").edges_by_doc["d"][0]
    assert up.null is False and up.obj.direction == "DOWN" and up.subj.direction == "UP"
    same = load_graph(_wrapper(tmp_path, {"causal_language": "direct_causal"}, "unchanged"), "d").edges_by_doc["d"][0]
    assert same.obj.direction == "NONE"


def test_the_real_murphy_gold_quirks_are_normalised():
    edges = load_graph(MURPHY, DOC).edges_by_doc[DOC]
    nulls = [e for e in edges if e.null]
    assert len(nulls) == 15
    assert sum(1 for e in nulls if e.causal_language != "no_relationship") == 3          # negated without no_relationship
    assert {e.obj.direction for e in nulls} == {"NONE"}                                   # 'unchanged' objects included


# ------------------------------------------------------------------------------------------ collapse mode
def test_collapse_merges_the_8_duplicate_subject_predicate_object_edges_in_murphy():
    edges = load_graph(MURPHY, DOC).edges_by_doc[DOC]
    merged = collapse(edges)
    assert len(edges) == 72 and len(merged) == 64
    keys = [(e.subj.key(), e.predicate, e.obj.key(), e.null) for e in merged]
    assert len(keys) == len(set(keys))                                    # unique pairs only
    assert sum(len(e.merged_ids) for e in merged) == 72                   # nothing lost
    assert any(len(e.merged_ids) > 1 and e.dose_level for e in merged)    # the dose levels were merged


def test_collapse_mode_changes_the_counts_but_not_the_self_score(murphy_graph, tmp_path):
    res = run(murphy_graph, tmp_path)
    assert res["modes"]["raw"]["micro"]["n_gold"] == 72 and res["modes"]["collapse"]["micro"]["n_gold"] == 64


# ------------------------------------------------------------------------------------------ plumbing
def test_validity_checks_find_the_planted_problems():
    g = {"source_documents": [{"document_id": "D"}],
         "nodes": [{"id": "a", "entity_term": "FOO:1", "name": "A"}, {"id": "a", "name": "A2"},
                   {"id": "b", "name": "B", "state_or_change_qualifier": "unchanged", "measured_attribute": "PATO:0000070"}],
         "edges": [{"id": "e1", "subject": "a", "object": "zzz", "predicate": "causes", "source_document": "X"},
                   {"id": "e1", "subject": "a", "object": "b", "predicate": "causes", "negated": True,
                    "causal_language": "uncertain_causal", "dose": {"unit": "http://x/y"},
                    "mediation": {"mediator_node_ids": ["nope"]}},
                   {"id": "e3", "subject": "a", "object": "b", "predicate": "causes", "negated": True,
                    "causal_language": "no_relationship"}]}
    c = validity_checks([g])["counts"]
    assert c["dangling_object"] == 1 and c["dangling_mediator"] == 1 and c["dangling_source_document"] == 1
    assert c["duplicate_node_ids"] == 1 and c["duplicate_edge_ids"] == 1
    assert c["negated_without_no_relationship"] == 1 and c["unchanged_on_null_object"] == 2
    assert c["bad_dose_unit"] == 1 and c["undeclared_prefix"] == 1


def test_gold_doc_id_binds_to_the_preceding_gold_and_doc_map_is_used(tmp_path, murphy_graph):
    murphy_graph = copy.deepcopy(murphy_graph)
    for e in murphy_graph["edges"]:
        e["source_document"] = "YKQQZV93"
    pred = tmp_path / "pred.yaml"
    pred.write_text(yaml.safe_dump(murphy_graph, sort_keys=False), encoding="utf-8")
    dm = tmp_path / "map.csv"
    dm.write_text("gold_doc,pred_doc\nmurphy2005,YKQQZV93\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = cli.main(["--gold", str(MURPHY), "--gold-doc-id", DOC, "--pred", str(pred), "--doc-map", str(dm), "--out", str(out)])
    assert rc == 0 and (out / "score.md").exists() and (out / "score.json").exists()
    assert load_doc_map(dm) == {"murphy2005": "YKQQZV93"}
    import json
    j = json.loads((out / "score.json").read_text())
    assert j["score"]["modes"]["raw"]["micro"]["levels"]["standard"]["f1"] == pytest.approx(1.0)


def test_documents_missing_from_the_prediction_score_zero_recall_and_other_docs_are_ignored(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    for e in g["edges"]:
        e["source_document"] = "somebody_else"
    ge, gf = gold_murphy()
    res = score(ge, gf, pred_from(g, tmp_path))
    assert lv(res, "raw", "standard", "recall") == 0.0
    assert res["unscored_pred_docs"] == ["somebody_else"]
    assert "warning" in res["modes"]["raw"]["docs"][DOC]


def test_tokens_add_f1_per_1k_tokens(murphy_graph, tmp_path):
    ge, gf = gold_murphy()
    res = score(ge, gf, pred_from(murphy_graph, tmp_path), tokens={DOC: (3000, 1000)})
    t = res["modes"]["raw"]["tokens"]
    assert t["mean_tokens_per_paper"] == 4000 and t["f1_per_1k_tokens"] == pytest.approx(0.25)


def test_weakened_prediction_scores_between_zero_and_one(murphy_graph, tmp_path):
    g, log = weaken(murphy_graph, seed=7)
    res = run(g, tmp_path)
    f1 = lv(res, "raw", "standard")
    assert 0.2 < f1 < 0.9 and log["edges_deleted"] == 24
    assert res["modes"]["raw"]["micro"]["null"]["recall"] < 1.0


# ------------------------------------------------------------------------------------------ gated levels
def _synthetic(rows, doc="D"):
    """rows: (subject_taxon, subject_qualifier, object_taxon, object_attribute, object_qualifier[, extra edge fields])."""
    nodes, edges = [], []
    for k, r in enumerate(rows):
        st, sq, ot, oa, oq = r[:5]
        extra = r[5] if len(r) > 5 else {}
        nodes.append({"id": f"s{k}", "name": f"driver {k}", "entity_type": "taxon", "entity_term": st, "state_or_change_qualifier": sq})
        node = {"id": f"o{k}", "name": f"response {k}", "entity_type": "taxon", "entity_term": ot, "state_or_change_qualifier": oq}
        if oa:
            node["measured_attribute"] = oa
        nodes.append(node)
        edges.append(dict({"id": f"e{k}", "subject": f"s{k}", "object": f"o{k}", "predicate": "causes",
                           "causal_language": "direct_causal", "source_document": doc}, **extra))
    return {"nodes": nodes, "edges": edges, "source_documents": [{"document_id": doc}]}


def _score_pair(gold_rows, pred_rows, tmp_path, threshold=0.5):
    ge = pred_from(_synthetic(gold_rows), tmp_path, "g.yaml")
    pe = pred_from(_synthetic(pred_rows), tmp_path, "p.yaml")
    return score(ge, {}, pe, None, threshold)


S, O = "NCBITaxon:3472", "NCBITaxon:126270"


def test_weakened_murphy_with_shuffled_attributes_standard_and_strict_precision_fall_far_below_loose(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    idx = [i for i, n in enumerate(g["nodes"]) if n.get("measured_attribute")]
    vals = [g["nodes"][i]["measured_attribute"] for i in idx]
    random.Random(5).shuffle(vals)
    for i, v in zip(idx, vals):
        g["nodes"][i]["measured_attribute"] = v
    res = run(g, tmp_path)
    loose, std, strict = (lv(res, "raw", l, "precision") for l in ("loose", "standard", "strict"))
    assert loose == pytest.approx(1.0)               # still the right pairs of entities
    assert std < 0.6 and strict < 0.6                # ...but the wrong variables
    assert std < loose - 0.4
    full, _ = weaken(murphy_graph, seed=7)           # the standard weakened prediction as well
    res = run(full, tmp_path)
    assert lv(res, "raw", "loose", "precision") == pytest.approx(1.0)
    assert lv(res, "raw", "standard", "precision") < 0.7


def test_paraphrased_attributes_keep_standard_and_strict_f1_at_one(tmp_path):
    gold = [(S, "introduced", O, "number", "decreased"), (S, "introduced", "NCBITaxon:3330", "height", "decreased"),
            (S, "introduced", "NCBITaxon:52299", "richness", "increased"), (S, "introduced", "NCBITaxon:4081", "abundance", "decreased")]
    pred = [(S, "introduced", O, "count", "decreased"), (S, "introduced", "NCBITaxon:3330", "plant height", "decreased"),
            (S, "introduced", "NCBITaxon:52299", "species richness", "increased"),
            (S, "introduced", "NCBITaxon:4081", "number of individuals", "decreased")]
    res = _score_pair(gold, pred, tmp_path)
    for level in ("loose", "standard", "strict"):
        assert lv(res, "raw", level) == pytest.approx(1.0), level


def test_paraphrased_attributes_in_murphy_keep_standard_f1_at_one(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    swap = {"count": "number of individuals", "initial density": "planting density"}
    changed = 0
    for n in g["nodes"]:
        if n.get("measured_attribute") in swap:
            n["measured_attribute"] = swap[n["measured_attribute"]]
            changed += 1
    assert changed >= 8
    res = run(g, tmp_path)
    for level in ("loose", "standard", "strict"):
        assert lv(res, "raw", level) == pytest.approx(1.0), level


def test_attributes_foreign_to_the_species_pair_no_longer_cross_match(tmp_path):
    # gold: two claims about the same species pair, different variables.  Prediction: one foreign variable, one synonym.
    gold = [(S, "introduced", O, "count", "decreased"), (S, "introduced", O, "height", "decreased")]
    pred = [(S, "introduced", O, "richness", "decreased"), (S, "introduced", O, "abundance", "decreased")]
    res = _score_pair(gold, pred, tmp_path)
    assert lv(res, "raw", "loose", "tp") == 2                      # right entities for both
    assert lv(res, "raw", "standard", "tp") == 1                   # only the synonym (abundance ~ count) is right
    assert lv(res, "raw", "standard", "precision") == pytest.approx(0.5)
    fn = res["modes"]["raw"]["fn"]
    assert len(fn) == 1
    assert "attribute differs" in fn[0]["reason"]


def test_foreign_attributes_everywhere_in_murphy_do_not_cross_match(murphy_graph, tmp_path):
    g = copy.deepcopy(murphy_graph)
    for n in g["nodes"]:
        if n.get("measured_attribute"):
            n["measured_attribute"] = "soil pH"
    res = run(g, tmp_path)
    assert lv(res, "raw", "loose", "precision") == pytest.approx(1.0)
    assert lv(res, "raw", "standard", "precision") < 0.15


def test_gates_in_isolation(tmp_path):
    base = (S, "introduced", O, "count", "decreased")
    # opposite direction: loose yes, standard no
    r = _score_pair([base], [(S, "introduced", O, "count", "increased")], tmp_path)
    assert lv(r, "raw", "loose", "tp") == 1 and lv(r, "raw", "standard", "tp") == 0
    # 'unchanged' / missing is not opposite: standard yes, strict no
    r = _score_pair([base], [(S, "introduced", O, "count", "present")], tmp_path)
    assert lv(r, "raw", "standard", "tp") == 1 and lv(r, "raw", "strict", "tp") == 0
    # subject attribute and direction are not gated
    r = _score_pair([base], [(S, "removed", O, "count", "decreased")], tmp_path)
    assert lv(r, "raw", "strict", "tp") == 1
    # different object entity: nothing matches
    r = _score_pair([base], [(S, "introduced", "NCBITaxon:3330", "count", "decreased")], tmp_path)
    assert lv(r, "raw", "loose", "tp") == 0
    # null flag disagreement: nothing matches
    r = _score_pair([base], [(S, "introduced", O, "count", "decreased", {"negated": True, "causal_language": "no_relationship"})], tmp_path)
    assert lv(r, "raw", "loose", "tp") == 0


def test_threshold_only_moves_the_standard_level(tmp_path):
    gold = [(S, "introduced", O, "seedling count", "decreased")]
    pred = [(S, "introduced", O, "count", "decreased")]            # Jaccard({seedling,@count}, {@count}) = 0.5
    lo = _score_pair(gold, pred, tmp_path, threshold=0.5)
    hi = _score_pair(gold, pred, tmp_path, threshold=0.6)
    assert lv(lo, "raw", "standard", "tp") == 1 and lv(hi, "raw", "standard", "tp") == 0
    assert lv(hi, "raw", "loose", "tp") == 1
    assert lo["sensitivity"]["raw"]["0.5"]["f1"] == 1.0 and lo["sensitivity"]["raw"]["0.6"]["f1"] == 0.0
