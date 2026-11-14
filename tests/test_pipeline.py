"""Unit tests for stages 2-6 (no network, no endpoint)."""
import csv
import copy
import json
import re
from pathlib import Path

import pytest

from pipeline import extract as ex
from pipeline.expand import expand_claims
from pipeline.extract import (Client, ConfigError, LLMConfig, LLMError, config_from_env, extract_paper, load_prompt, split_user_text,
                              strip_thinking)
from pipeline.grounding import taxon_id, term_id, unverified_terms
from pipeline.guard import (final_integrity, guard_paper, merge, repair_edge, source_document, validate_edge, validate_graph,
                            wrapper_graph)
from pipeline.parse import ParseError, check_sentences, parse_line, parse_sentences, parse_text, parse_var
from pipeline.write import write_outputs, validate_outputs

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (ROOT / "pipeline" / "prompt" / "system.txt").read_text(encoding="utf-8")
EXAMPLES = [ln for ln in PROMPT.split("EXAMPLES")[1].splitlines() if ln.strip()]


def sidecar(n=70):
    sents = [{"n": i, "section": ["abs", "res", "dis"][i % 3], "start_char": i * 100, "end_char": i * 100 + 90,
              "raw": f"raw {i}", "clean": f"Sentence {i} density was higher than in controls (P = 0.01, ANOVA), because of rain.",
              "compressed": f"Sentence {i} density was higher [sig]."} for i in range(1, n + 1)]
    species = [{"id": "T1", "name": "Sanguinaria canadensis", "ncbitaxon": "NCBITaxon:3472"},
               {"id": "T2", "name": "Alliaria petiolata", "ncbitaxon": "NCBITaxon:126270"},
               {"id": "T3", "name": "Rodentia sp.", "ncbitaxon": None}]
    return {"sentences": sents, "species": species, "context": "randomized blocks sampled monthly for four years"}


def expand(lines, side=None):
    claims, bad = parse_text("\n".join(lines))
    assert not bad
    return expand_claims("DOC", claims, side or sidecar())


# =================================================================================== parser
def test_all_six_prompt_examples_parse():
    claims, bad = parse_text("\n".join(EXAMPLES))
    assert len(claims) == 6 and not bad
    f12 = claims[0]
    assert f12.kind == "F" and f12.sentences == [12] and f12.predicate == "c" and f12.language == "D" and f12.design == "exp"
    assert [(e.thing, e.prop, e.change) for e in f12.effects] == [("T2", "number of individuals", "-"), ("T2", "height", "-")]
    assert f12.keys == {"stage": "seedling", "dose": "9-11 ramets/m2"}
    n19 = claims[1]
    assert n19.kind == "N" and n19.language is None and n19.effects[0].change is None


def test_management_action_three_part_and_four_part_forms():
    a = parse_var("planting(T1)/occ/mgmt")                    # thing/change/type
    assert (a.thing, a.prop, a.change, a.vtype) == ("planting(T1)", None, "occ", "mgmt")
    b = parse_var("T1/initial planting density/+/tax")        # thing/property/change/type
    assert (b.thing, b.prop, b.change, b.vtype) == ("T1", "initial planting density", "+", "tax")
    c = parse_var("T2/number of individuals/-")               # thing/property/change
    assert (c.prop, c.change, c.vtype) == ("number of individuals", "-", None)
    d = parse_var("T2/height/")                               # missing optional change/type
    assert (d.prop, d.change) == ("height", None)
    assert parse_var("T2/a/b/c/d") is None and parse_var("") is None


def test_messy_lines_are_tolerated():
    lines = [
        "  F | 12, 14 | T1 / initial planting density / increased / taxon | causes | T2 / height / decreased | direct_causal | experiment |  stage = seedling ",
        "F|12-14|T1/density/+|c|T2/cover/-|D|exp",
        "F|[7]|T1/density/+|ct|T2/cover/-|uncertain|observational|season=summer",
        "N|3|T1/density/+|c|T2/cover|D|exp",                  # language field on an N line
        "F|9|T1/density/+|a|T2/cover/-|associational|obs",
        "F|9|T1/density/+|correlated_with|T2/cover/-|A|obs",
    ]
    claims, bad = parse_text("\n".join(lines))
    assert not bad and len(claims) == 6
    assert claims[0].sentences == [12, 14] and claims[0].cause.change == "+" and claims[0].cause.vtype == "tax"
    assert claims[0].predicate == "c" and claims[0].language == "D" and claims[0].design == "exp" and claims[0].keys == {"stage": "seedling"}
    assert claims[1].sentences == [12, 13, 14]
    assert claims[2].language == "U" and claims[2].design == "obs" and claims[2].keys["season"] == "summer"
    assert claims[3].kind == "N" and claims[3].language is None and claims[3].design == "exp"
    assert claims[5].predicate == "cw"


def test_prose_blank_and_fenced_lines_are_ignored():
    text = "Here are the claims:\n\n```\nF|1|T1/density/+|c|T2/cover/-|D|exp\n```\nHope this helps!\n- F|2|x|c|y|D|exp\n"
    claims, bad = parse_text(text)
    assert len(claims) == 1 and not bad


@pytest.mark.parametrize("line", [
    "F|1|T1/density/+|c|T2/cover/-",                          # too few fields
    "F|x|T1/density/+|c|T2/cover/-|D|exp",                    # no sentence numbers
    "F|1|T1/density/+|zzz|T2/cover/-|D|exp",                  # unknown predicate
    "F|1|T1/density/+|c|T2/cover/-|Q|exp",                    # unknown language
    "F|1|T1/density/+|c|T2/cover/-|D|banana",                 # unknown design
    "F|1|T1/a/b/c/d/e|c|T2/cover/-|D|exp",                    # too many parts
    "F|1||c|T2/cover/-|D|exp",                                # empty cause
])
def test_broken_lines_are_collected_not_raised(line):
    claims, bad = parse_text("F|1|T1/density/+|c|T2/cover/-|D|exp\n" + line)
    assert len(claims) == 1 and bad == [line]
    with pytest.raises(ParseError):
        parse_line(line)


def test_sentence_numbers_and_unknown_sentences_dropped():
    assert parse_sentences("3-5, 9") == [3, 4, 5, 9] and parse_sentences("12 14;15") == [12, 14, 15] and parse_sentences("a,b") == []
    claims, _ = parse_text("F|1,99|T1/a/+|c|T2/b/-|D|exp\nF|98-99|T1/a/+|c|T2/b/-|D|exp")
    kept, dropped = check_sentences(claims, range(1, 71))
    assert len(kept) == 1 and kept[0].sentences == [1] and dropped == 1


# =================================================================================== expansion
def test_every_prompt_example_expands_into_valid_camo_with_no_edge_dropped():
    out = expand(EXAMPLES)
    nodes, edges, stats = guard_paper("DOC", out.nodes, out.edges)
    assert len(edges) == len(out.edges) == 9                  # F12 -> 2, N19, F33 -> parent + 2 path edges, F41, F52, F60
    assert not [k for k in stats if k.startswith(("dropped edge", "field", "repair"))], dict(stats)
    assert validate_graph({**wrapper_graph(list(nodes.values()), edges)}) is None
    assert all(e["source_document"] == "DOC" and e["philosophical_accounts"] for e in edges)


def test_f12_two_effects_dose_stage_and_experiment_features():
    out = expand([EXAMPLES[0]])
    e1, e2 = out.edges
    assert (e1["predicate"], e1["causal_language"]) == ("causes", "direct_causal") and e1["subject"] == e2["subject"]
    assert e1["dose"] == {"minimum_value": 9.0, "maximum_value": 11.0, "unit_text": "ramets/m2", "verbatim": "9-11 ramets/m2"}
    assert "unit" not in e1["dose"]
    assert e1["direction"] == {"status": "asserted", "evidence_for_direction": "experimental"}
    assert "interventionist" in e1["philosophical_accounts"] and "counterfactual" in e1["philosophical_accounts"]
    assert e1["evidential_basis"]["evidence_types"] == ["randomized_experiment"]       # context says "randomized"
    assert e1["strength"] == {"status": "explicitly_asserted", "significance": "significant", "p_value": 0.01, "analysis_method": "anova"}
    subj, obj = out.nodes[e1["subject"]], out.nodes[e1["object"]]
    assert subj["entity_term"] == "NCBITaxon:3472" and subj["entity_type"] == "taxon" and subj["state_or_change_qualifier"] == "increased"
    assert subj["name"] == "Increased initial planting density of Sanguinaria canadensis"
    assert obj["entity_term"] == "NCBITaxon:126270" and obj["measured_attribute"] == "PATO:0000070"   # verified term
    assert obj["state_or_change_qualifier"] == "decreased" and obj["life_stage"] == "germinant_or_seedling"
    assert obj["source_spans"][0]["section"] == "abstract" and obj["source_spans"][0]["start_char"] == 1200


def test_n_line_is_a_negated_null_result_with_no_unchanged_qualifier():
    out = expand([EXAMPLES[1]])
    e = out.edges[0]
    assert e["negated"] is True and e["causal_language"] == "no_relationship"
    assert "state_or_change_qualifier" not in out.nodes[e["object"]]                  # effect given without a change
    assert e["temporal_extent"] == {"observation_seasons": ["early_spring"]}
    # a stable effect on an N line is dropped, never written as 'unchanged'
    o2 = expand(["N|5|T1/density/+|c|T2/cover/=|exp"]).edges[0]
    assert "state_or_change_qualifier" not in expand(["N|5|T1/density/+|c|T2/cover/=|exp"]).nodes[o2["object"]]
    # a given change is kept
    o3 = expand(["N|5|T1/density/+|c|T2/cover/-|exp"])
    assert o3.nodes[o3.edges[0]["object"]]["state_or_change_qualifier"] == "decreased"


def test_mediation_creates_a_mediator_node_and_two_path_edges():
    out = expand([EXAMPLES[2]])
    parent, a, b = out.edges
    mid = parent["mediation"]["mediator_node_ids"][0]
    assert parent["mediation"]["status"] == "explicitly_asserted"
    assert (a["subject"], a["object"]) == (parent["subject"], mid) and (b["subject"], b["object"]) == (mid, parent["object"])
    assert a["causal_language"] == parent["causal_language"] and "mediation" not in a
    assert parent["evidential_basis"]["evidence_objects"] == ["both"]
    m = out.nodes[mid]
    assert m["entity_term"] == "leafing" and m["entity_type"] == "environmental_process"
    assert m["applied_to"] == [{"entity_type": "taxon", "entity_term": "NCBITaxon:3472"}] and m["state_or_change_qualifier"] == "occurred"
    assert parent["dose"]["numeric_value"] == 7.0


def test_management_action_line_41():
    out = expand([EXAMPLES[3]])
    e = out.edges[0]
    s = out.nodes[e["subject"]]
    assert s["entity_type"] == "management_intervention" and s["entity_term"] == "planting" and s["state_or_change_qualifier"] == "occurred"
    assert s["applied_to"] == [{"entity_type": "taxon", "entity_term": "NCBITaxon:3472"}] and "measured_attribute" not in s
    assert (e["predicate"], e["causal_language"], e["scope"], e["dose_level"]) == ("prevents", "uncertain_causal", "contingent", "intermediate")
    assert "agency" in e["philosophical_accounts"] and e["evidential_basis"]["evidence_types"] == ["expert_judgment"]
    assert e["strength"]["significance"] == "significant"      # marker wins in this synthetic sentence


def test_comparator_guild_and_associational_line_52_and_process_line_60():
    out = expand(EXAMPLES[4:6])
    a, b = out.edges
    assert a["comparator"] == [{"status": "explicitly_asserted", "comparator_type": "untreated_control", "comparator_description": "uncaged plots"}]
    assert out.nodes[a["subject"]]["name"] == "Introduction of small-mammal exclosure"
    assert out.nodes[a["subject"]]["entity_type"] == "management_intervention"
    eff = out.nodes[a["object"]]
    assert eff["entity_type"] == "composite_variable" and eff["entity_term"] == "planted native species"
    assert a["causal_language"] == "associational" and a["predicate"] == "associated_with"
    assert (b["predicate"], b["causal_language"]) == ("contributes_to", "uncertain_causal")
    assert out.nodes[b["subject"]]["entity_type"] == "environmental_process" and out.nodes[b["subject"]]["applied_to"][0]["entity_term"] == "Rodentia sp."


def test_entity_type_defaults_when_no_type_code_is_given():
    out = expand(["F|1|mowing/occ|c|invasion(T2)/spread/-|U|exp", "F|2|plant community/richness/+|c|soil moisture/level/-|U|obs"])
    kinds = {n["name"]: n["entity_type"] for n in out.nodes.values()}
    assert kinds["Occurrence of mowing"] == "management_intervention"
    assert [t for n, t in kinds.items() if "invasion" in n] == ["environmental_process"]
    assert [t for n, t in kinds.items() if "plant community" in n] == ["composite_variable"]
    assert [t for n, t in kinds.items() if "soil moisture" in n] == ["environmental_variable"]


def test_dose_parsing_variants():
    from pipeline.expand import Expander
    p = Expander.parse_dose
    assert p("as little as 5 ramets/m2")["minimum_value"] == 5.0
    assert p("above 7 ramets/m2")["minimum_value"] == 7.0
    assert p("below 3 plants")["maximum_value"] == 3.0
    assert p("5") == {"numeric_value": 5.0, "verbatim": "5"}
    assert p("high") is None


def test_expansion_emits_an_id_only_for_verified_rows():
    out = expand(["F|1|T1/density/+|c|T2/abundance/-|D|exp", "F|2|T1/height/+|c|T2/intensity/-|U|obs",
                  "F|3|soil/precipitation/+|c|T2/persistence/-|U|obs"])
    attrs = {n["name"]: n.get("measured_attribute") for n in out.nodes.values()}
    assert attrs["Increased density of Sanguinaria canadensis"] == "density"                  # no ID: stays free text
    assert attrs["Decreased abundance of Alliaria petiolata"] == "PATO:0000070"               # verified=yes
    assert attrs["Increased height of Sanguinaria canadensis"] == "PATO:0000119"              # verified=yes
    assert attrs["Decreased intensity of Alliaria petiolata"] == "intensity"                  # verified=no -> free text
    assert attrs["Decreased persistence of Alliaria petiolata"] == "persistence"
    assert attrs["Increased precipitation of soil"] == "precipitation"                        # precipitation has no ID
    soil = next(n for n in out.nodes.values() if n["name"].endswith("of soil"))
    assert soil["entity_term"] == "ENVO:00001998"                                             # entity-kind row, verified


def test_term_table_decisions_as_agreed():
    rows = {r["synonym"]: r for r in csv.DictReader(open(ROOT / "data" / "terms.tsv", encoding="utf-8"), delimiter="\t")}
    yes = {"height": "PATO:0000119", "length": "PATO:0000122", "diameter": "PATO:0001334", "width": "PATO:0000921",
           "depth": "PATO:0001595", "thickness": "PATO:0000915", "area": "PATO:0001323", "volume": "PATO:0000918",
           "mass": "PATO:0000125", "size": "PATO:0000117", "age": "PATO:0000011", "temperature": "PATO:0000146",
           "rate": "PATO:0000161", "frequency": "PATO:0000044", "soil": "ENVO:00001998", "canopy": "ENVO:01001242",
           "fire": "ENVO:01000786", "season": "ENVO:03000096", "abundance": "PATO:0000070", "number of individuals": "PATO:0000070"}
    for s, c in yes.items():
        assert (rows[s]["curie"], rows[s]["verified"]) == (c, "yes"), s
    assert rows["abundance"]["label"] == "amount (used for abundance per README/schema examples)"
    for s in ("intensity", "persistence"):
        assert rows[s]["verified"] == "no" and rows[s]["curie"]
    for s in ("density", "precipitation"):
        assert rows[s]["verified"] == "no" and rows[s]["curie"] == ""
    assert not [s for s, r in rows.items() if r["curie"] in ("PATO:0000574", "PATO:0001019")]


def test_term_lookup_ignores_unverified_empty_and_wrong_kind_rows(tmp_path):
    p = tmp_path / "terms.tsv"
    p.write_text("synonym\tcurie\tlabel\tkind\tverified\nheight\tPATO:0000119\theight\tattribute\tyes\n"
                 "soil\tENVO:00001998\tsoil\tentity\tyes\nintensity\tPATO:0000049\tintensity\tattribute\tno\n"
                 "density\t\tdensity\tattribute\tyes\n", encoding="utf-8")
    sp = str(p)
    assert term_id("Height ", "attribute", sp) == "PATO:0000119"
    assert term_id("height", "entity", sp) is None                    # wrong kind
    assert term_id("soil", "entity", sp) == "ENVO:00001998"
    assert term_id("intensity", "attribute", sp) is None              # verified=no
    assert term_id("density", "attribute", sp) is None                # verified=yes but no ID: still free text
    assert {r["synonym"] for r in unverified_terms(sp)} == {"intensity", "density"}


def test_grounding_taxon_lookup():
    assert taxon_id("Alliaria petiolata") == "NCBITaxon:126270"
    assert taxon_id("alliaria PETIOLATA") == "NCBITaxon:126270"
    assert taxon_id("Alliaria petiolata (M. Bieb.) Cavara & Grande") == "NCBITaxon:126270"
    assert taxon_id("No such species") is None and taxon_id(None) is None


# =================================================================================== guard
def good_graph():
    out = expand([EXAMPLES[0]])
    return out.nodes, out.edges


def edge_with(**kw):
    nodes, edges = good_graph()
    e = copy.deepcopy(edges[0])
    e.update(kw)
    return nodes, e


def test_guard_repair_causes_with_associational_becomes_associated_with():
    nodes, e = edge_with(causal_language="associational")
    _, edges, stats = guard_paper("DOC", nodes, [e])
    assert edges[0]["predicate"] == "associated_with" and stats["repair: causes+associational->associated_with"] == 1


@pytest.mark.parametrize("pred", ["associated_with", "correlated_with", "precedes"])
@pytest.mark.parametrize("lang", ["direct_causal", "uncertain_causal"])
def test_guard_repair_non_causal_predicate_with_causal_language_becomes_contributes_to(pred, lang):
    nodes, e = edge_with(predicate=pred, causal_language=lang)
    _, edges, _ = guard_paper("DOC", nodes, [e])
    assert edges[0]["predicate"] == "contributes_to" and edges[0]["causal_language"] == lang


def test_guard_repair_correlated_with_needs_a_correlation_statistic():
    nodes, e = edge_with(predicate="correlated_with", causal_language="associational", original_sentence="Cover rose with density.")
    assert guard_paper("DOC", nodes, [e])[1][0]["predicate"] == "associated_with"
    nodes, e = edge_with(predicate="correlated_with", causal_language="associational", original_sentence="Cover rose with density (r = 0.8).")
    assert guard_paper("DOC", nodes, [e])[1][0]["predicate"] == "correlated_with"


def test_guard_drops_an_invalid_optional_field_and_keeps_the_edge():
    nodes, e = edge_with(scope="bogus", dose_level="enormous")
    e["strength"]["significance"] = "sort_of"
    _, edges, stats = guard_paper("DOC", nodes, [e])
    assert len(edges) == 1 and "scope" not in edges[0] and "dose_level" not in edges[0]
    assert "significance" not in edges[0]["strength"] and edges[0]["strength"]["status"] == "explicitly_asserted"
    assert stats["field dropped scope"] == 1 and stats["field dropped strength.significance"] == 1


def test_guard_drops_an_invalid_optional_node_field():
    nodes, e = edge_with()
    nodes[e["object"]]["life_stage"] = "teenager"
    cleaned, edges, _ = guard_paper("DOC", nodes, [e])
    assert len(edges) == 1 and "life_stage" not in cleaned[e["object"]]


def test_guard_drops_the_edge_when_a_required_field_is_broken():
    nodes, e = edge_with(predicate="not_a_predicate")
    assert guard_paper("DOC", nodes, [e])[1] == []
    nodes, e = edge_with()
    del e["philosophical_accounts"]
    assert guard_paper("DOC", nodes, [e])[1] == []
    nodes, e = edge_with(subject="node:missing")
    _, edges, stats = guard_paper("DOC", nodes, [e])
    assert edges == [] and stats["dropped edge: dangling"] == 1


def test_guard_integrity_negation_unchanged_object_unused_nodes_and_duplicates():
    nodes, e = edge_with(negated=True, causal_language="direct_causal")
    nodes[e["object"]]["state_or_change_qualifier"] = "unchanged"
    nodes["node:DOC_unused"] = {"id": "node:DOC_unused", "name": "Unused", "entity_term": "x"}
    dup = copy.deepcopy(e)
    cleaned, edges, stats = guard_paper("DOC", nodes, [e, dup])
    assert len(edges) == 1 and edges[0]["causal_language"] == "no_relationship" and edges[0]["negated"] is True
    assert "state_or_change_qualifier" not in cleaned[e["object"]]
    assert "node:DOC_unused" not in cleaned and stats["dropped edge: duplicate id"] == 1
    assert stats["dropped nodes: unused"] == 2                            # DOC_unused and the second effect node of the F12 example
    nodes, e = edge_with(causal_language="no_relationship")
    assert guard_paper("DOC", nodes, [e])[1][0]["negated"] is True
    nodes, e = edge_with(source_document="OTHER")
    assert guard_paper("DOC", nodes, [e])[1] == []


def test_guard_undeclared_prefix_becomes_free_text():
    nodes, e = edge_with()
    nodes[e["subject"]]["entity_term"] = "FOO:123"
    nodes[e["object"]]["measured_attribute"] = "BAR:9"
    cleaned, edges, stats = guard_paper("DOC", nodes, [e])
    assert cleaned[e["subject"]]["entity_term"] == nodes[e["subject"]]["name"]
    assert "measured_attribute" not in cleaned[e["object"]]
    assert stats["repair: undeclared prefix in entity_term"] == 1 and stats["repair: undeclared prefix in measured_attribute"] == 1


def test_validate_edge_reports_unrepairable():
    nodes, e = edge_with()
    e["strength"] = "not an object"
    ok, _, notes = validate_edge(e, nodes)
    assert ok is not None and "strength" not in ok                         # an optional field: dropped, edge survives


# =================================================================================== merge / write
def index_rows():
    with open(ROOT / "corpus" / "index.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_merge_contains_every_index_document_even_when_extraction_failed_everywhere_else():
    rows = index_rows()
    assert len(rows) == 308
    nodes, edges = good_graph()
    n, e, _ = guard_paper("DOC", nodes, edges)
    slug = rows[5]["slug"]
    for x in e:
        x["source_document"] = slug
    g = merge(rows, {slug: (n, e)})
    assert [d["document_id"] for d in g["source_documents"]] == [r["slug"] for r in rows]
    assert all(d.get("doi") for d in g["source_documents"] if next(r for r in rows if r["slug"] == d["document_id"])["doi"].strip())
    assert {x["source_document"] for x in g["edges"]} <= {d["document_id"] for d in g["source_documents"]}
    assert validate_graph(g) is None and final_integrity(g) == []
    d0 = source_document(rows[0])
    assert isinstance(d0.get("year"), int) and isinstance(d0.get("authors"), list) and d0["document_id"] == rows[0]["slug"]


def test_merge_with_no_edges_fails_loudly():
    with pytest.raises(RuntimeError, match="no edges"):
        merge(index_rows(), {})


def test_final_integrity_catches_a_bad_source_document():
    nodes, edges = good_graph()
    n, e, _ = guard_paper("DOC", nodes, edges)
    g = merge([{"slug": "DOC", "doi": "10.1/x", "title": "t", "authors": "A, B; C, D", "year": "2001", "journal": "J"}], {"DOC": (n, e)})
    assert final_integrity(g) == [] and g["source_documents"][0]["authors"] == ["A, B", "C, D"]
    g["edges"][0]["source_document"] = "NOPE"
    assert any("not in source_documents" in p for p in final_integrity(g))


def test_written_files_validate_and_have_no_yaml_aliases(tmp_path):
    nodes, edges = good_graph()
    n, e, _ = guard_paper("DOC", nodes, edges)
    g = merge([{"slug": "DOC", "doi": "10.1/x", "title": "t", "authors": "A, B", "year": "2001", "journal": "J"}], {"DOC": (n, e)})
    yp, jp = write_outputs(g, tmp_path)
    assert "&id" not in yp.read_text(encoding="utf-8") and "*id" not in yp.read_text(encoding="utf-8")
    errors, note = validate_outputs(g, yp, jp, linkml=False)
    assert errors == [] and "JSON Schema" in note


# =================================================================================== extract.py: client, cache, chunks, prompt
def cfg(tmp_path, **kw):
    return LLMConfig(url="http://x/v1", model="m", key="secret-key", cache_dir=tmp_path / "cache", **kw)


def reply(text, pt=100, ct=20):
    return 200, {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": pt, "completion_tokens": ct}}


def test_config_from_env_names_what_is_missing_and_never_the_values(monkeypatch):
    for v in ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("BRINE_API_KEY", "supersecret")
    with pytest.raises(ConfigError) as e:
        config_from_env()
    assert "BRINE_URL" in str(e.value) and "BRINE_MODEL" in str(e.value) and "supersecret" not in str(e.value)
    monkeypatch.setenv("BRINE_URL", "http://h/v1/")
    monkeypatch.setenv("BRINE_MODEL", "qwen")
    c = config_from_env()
    assert c.url == "http://h/v1" and "supersecret" not in repr(c)


def test_prompt_flag_picks_a_file_and_rejects_paths():
    name, text = load_prompt()
    assert name == "system.txt" and text.startswith("You annotate causal claims") and "ask yourself" not in text
    name, text = load_prompt("system_socratic")
    assert name == "system_socratic.txt" and "ask yourself" in text
    for bad in ("../x.txt", "/etc/passwd", "a/b.txt", ".hidden", "missing.txt"):
        with pytest.raises(ConfigError):
            load_prompt(bad)


def test_thinking_off_sends_kwargs_and_think_blocks_are_stripped(tmp_path):
    seen = []
    def post(url, payload):
        seen.append((url, payload))
        return reply("<think>hmm</think>\nF|1|T1/a/+|c|T2/b/-|D|exp")
    c = Client(cfg(tmp_path), sleep=lambda s: None, post=post)
    r = c.complete("sys", "user")
    assert r.text == "F|1|T1/a/+|c|T2/b/-|D|exp" and r.prompt_tokens == 100 and r.completion_tokens == 20
    url, p = seen[0]
    assert url == "http://x/v1/chat/completions" and p["chat_template_kwargs"] == {"enable_thinking": False}
    assert p["temperature"] == 0 and p["max_tokens"] == 3000 and p["model"] == "m"
    assert r.thinking_mode == "off (kwargs)"
    assert strip_thinking("<think>never closed") == "" and strip_thinking("a<think>x</think>b") == "ab"


def test_thinking_on_sends_no_kwargs(tmp_path):
    seen = []
    c = Client(cfg(tmp_path, thinking=True), sleep=lambda s: None, post=lambda u, p: (seen.append(p), reply("ok"))[1])
    assert c.complete("s", "u").thinking_mode == "on" and "chat_template_kwargs" not in seen[0]


def test_rejected_kwargs_fall_back_to_no_think_once_and_remember(tmp_path):
    seen = []
    def post(url, payload):
        seen.append(payload)
        if "chat_template_kwargs" in payload:
            return 400, {"error": {"message": "unknown field chat_template_kwargs"}}
        return reply("F|1|T1/a/+|c|T2/b/-|D|exp")
    c = Client(cfg(tmp_path), sleep=lambda s: None, post=post)
    r = c.complete("s", "first")
    assert r.thinking_mode == "off (/no_think)" and seen[-1]["messages"][1]["content"].startswith("/no_think\n")
    n = len(seen)
    c.complete("s", "second")
    assert len(seen) == n + 1 and "chat_template_kwargs" not in seen[-1] and seen[-1]["messages"][1]["content"].startswith("/no_think\n")


def test_retries_on_5xx_429_and_network_errors_with_backoff_then_gives_up(tmp_path):
    calls, sleeps = [], []
    script = [(503, {}), (429, {}), "boom", reply("ok")]
    def post(url, payload):
        calls.append(1)
        s = script.pop(0)
        if s == "boom":
            raise OSError("connection reset")
        return s
    c = Client(cfg(tmp_path), sleep=sleeps.append, post=post)
    assert c.complete("s", "u").text == "ok" and len(calls) == 4 and sleeps == [2, 4, 8]
    always = Client(cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=lambda u, p: (500, {}))
    with pytest.raises(LLMError):
        always.complete("s", "other")


def test_a_404_switches_to_the_v1_path_once(tmp_path):
    urls = []
    def post(url, payload):
        urls.append(url)
        return (404, {}) if url == "http://h/chat/completions" else reply("ok")
    c = Client(LLMConfig(url="http://h", model="m", key="k", cache_dir=tmp_path / "c"), sleep=lambda s: None, post=post)
    assert c.complete("s", "u").text == "ok" and urls == ["http://h/chat/completions", "http://h/v1/chat/completions"]
    c.complete("s", "u2")
    assert urls[-1] == "http://h/v1/chat/completions" and len(urls) == 3


def test_cache_reuses_responses_and_keys_on_thinking_and_prompt(tmp_path):
    n = []
    def post(url, payload):
        n.append(1)
        return reply("cached text", 11, 7)
    c = Client(cfg(tmp_path), sleep=lambda s: None, post=post)
    a = c.complete("s", "u")
    b = c.complete("s", "u")
    assert len(n) == 1 and b.cached and not a.cached and b.text == "cached text" and (b.prompt_tokens, b.completion_tokens) == (11, 7)
    c.complete("other system", "u")
    Client(cfg(tmp_path, thinking=True), sleep=lambda s: None, post=post).complete("s", "u")
    assert len(n) == 3
    nc = Client(cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=post)
    nc.complete("s", "u")
    assert len(n) == 4


def test_bad_lines_get_one_repair_call_and_unknown_sentences_are_dropped(tmp_path):
    replies = ["F|1|T1/a/+|c|T2/b/-|D|exp\nBROKEN F|2|x\nF|2|T1/a/+|zzz|T2/b/-|D|exp\nF|99|T1/a/+|c|T2/b/-|D|exp",
               "F|2|T1/a/+|c|T2/b/-|D|exp"]
    seen = []
    def post(url, payload):
        seen.append(payload["messages"][1]["content"])
        return reply(replies.pop(0))
    c = Client(cfg(tmp_path), sleep=lambda s: None, post=post)
    out = extract_paper(c, "sys", "TITLE: t\nSPECIES: \nCONTEXT: \nTEXT:\n[1] (abs) a\n[2] (abs) b\n", [1, 2])
    assert len(seen) == 2 and "BROKEN" not in seen[1] and "F|2|T1/a/+|zzz" in seen[1] and "Output only" in seen[1]
    assert sorted(cl.sentences for cl in out.claims) == [[1], [2]]
    assert out.n_bad == 1 or out.n_bad == 2
    assert out.n_dropped_sentences == 1 and out.prompt_tokens == 200 and out.completion_tokens == 40


def test_split_user_text_chunks_at_section_boundaries_and_repeats_the_header():
    header = "TITLE: t\nSPECIES: T1=x\nCONTEXT: c\nTEXT:\n"
    lines = [f"[{i}] ({'abs' if i <= 30 else 'res' if i <= 80 else 'dis'}) " + ("word " * 40) for i in range(1, 121)]
    user = header + "\n".join(lines) + "\n"
    assert split_user_text(user, 10 ** 6) == [user]
    chunks = split_user_text(user, 2500)
    assert len(chunks) > 1
    seen = []
    for ch in chunks:
        assert ch.startswith(header)
        nums = [int(m.group(1)) for m in re.finditer(r"^\[(\d+)\] ", ch, re.M)]
        assert nums == sorted(nums)
        seen += nums
        assert len(ch) / 3.5 <= 2500 + 200
    assert seen == list(range(1, 121))                                   # nothing lost, numbering kept
    first = chunks[0]
    assert "(abs)" in first and "(dis)" not in first


def test_api_key_never_reaches_logs_or_errors(tmp_path, caplog):
    c = Client(cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=lambda u, p: (500, {"error": {"message": "nope"}}))
    with pytest.raises(LLMError) as e:
        c.complete("s", "u")
    assert "secret-key" not in str(e.value) and "secret-key" not in caplog.text and "secret-key" not in repr(c.cfg)


# =================================================================================== whole run: failure isolation
def _fake_post_factory(fail_title_fragment=None, fail_all=False):
    def post(url, payload):
        user = payload["messages"][1]["content"]
        if fail_all or (fail_title_fragment and fail_title_fragment in user.split("\n", 1)[0]):
            return 500, {"error": {"message": "boom"}}
        nums = re.findall(r"^\[(\d+)\] ", user, re.M)
        text = "\n".join(f"F|{n}|local seed/density/+|c|plant community/cover/-|D|exp" for n in nums[:3])
        return 200, {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    return post


def _patch_client(monkeypatch, tmp_path, **kw):
    import pipeline.main as m
    for k, v in (("BRINE_URL", "http://h/v1"), ("BRINE_MODEL", "m"), ("BRINE_API_KEY", "k")):
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(m, "Client", lambda cfg, **k: Client(cfg, sleep=lambda s: None, post=_fake_post_factory(**kw), **k))
    return m


def test_one_failing_paper_does_not_stop_the_run_and_keeps_its_source_document(monkeypatch, tmp_path):
    rows = index_rows()[:3]
    m = _patch_client(monkeypatch, tmp_path, fail_title_fragment=rows[1]["title"][:30])
    out = tmp_path / "out"
    rc = m.run(ROOT / "corpus", out, docs=[r["slug"] for r in rows], concurrency=2, use_cache=False)
    assert rc == 0
    g = json.loads((out / "camo_graph.json").read_text(encoding="utf-8"))
    assert len(g["source_documents"]) == 308
    assert {e["source_document"] for e in g["edges"]} == {rows[0]["slug"], rows[2]["slug"]}
    log = json.loads((out / "run_log.json").read_text(encoding="utf-8"))
    failed = [p for p in log["papers"] if p["error"]]
    assert [p["doc"] for p in failed] == [rows[1]["slug"]] and "LLMError" in failed[0]["error"]
    assert (out / "tokens.csv").read_text().count("\n") == 4


def test_if_every_paper_fails_the_run_fails_loudly_and_writes_no_invalid_graph(monkeypatch, tmp_path, capsys):
    m = _patch_client(monkeypatch, tmp_path, fail_all=True)
    rc = m.main([str(ROOT / "corpus"), str(tmp_path / "out"), "--limit", "2", "--no-cache"])
    assert rc == 1 and "no edges at all" in capsys.readouterr().err
    assert not (tmp_path / "out" / "camo_graph.yaml").exists()


def test_missing_environment_exits_2_with_the_names_only(monkeypatch, tmp_path, capsys):
    import pipeline.main as m
    for v in ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    assert m.main([str(ROOT / "corpus"), str(tmp_path / "o")]) == 2
    assert "BRINE_URL" in capsys.readouterr().err


# =================================================================================== DOI fallback
from pipeline import doi as doimod


def _md(tmp_path, slug, lines):
    (tmp_path / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_doi_from_the_first_line_of_a_real_article():
    info = doimod.resolve({"slug": "4CB9X9XE", "doi": ""}, ROOT / "corpus")
    assert (info.doi, info.source, info.line) == ("10.1111/1365-2664.12886", "markdown", 1)


def test_index_doi_always_wins(tmp_path):
    _md(tmp_path, "A", ["doi: 10.1111/other.1"])
    info = doimod.resolve({"slug": "A", "doi": " 10.9999/index.doi "}, tmp_path)
    assert (info.doi, info.source) == ("10.9999/index.doi", "index")


def test_a_data_repository_doi_on_a_dryad_line_is_ignored(tmp_path):
    _md(tmp_path, "A", ["Data available at Dryad: https://doi.org/10.5061/dryad.abc123", "Article doi:10.1111/real.2020.1."])
    info = doimod.resolve({"slug": "A", "doi": ""}, tmp_path)
    assert info.doi == "10.1111/real.2020.1" and info.line == 2
    _md(tmp_path, "B", ["see zenodo 10.5281/zenodo.123", "figshare 10.6084/m9.figshare.9", "PANGAEA 10.1594/PANGAEA.1"])
    assert doimod.resolve({"slug": "B", "doi": ""}, tmp_path).source == "none"


def test_two_different_candidates_give_none_but_the_same_doi_twice_is_fine(tmp_path):
    _md(tmp_path, "A", ["doi: 10.1111/aaa.1", "also cited: 10.2222/bbb.2"])
    assert doimod.resolve({"slug": "A", "doi": ""}, tmp_path).source == "none"
    _md(tmp_path, "B", ["[10.1111/aaa.1](https://doi.org/10.1111/AAA.1)."])
    info = doimod.resolve({"slug": "B", "doi": ""}, tmp_path)
    assert info.source == "markdown" and info.doi.lower() == "10.1111/aaa.1"


@pytest.mark.parametrize("line,expected", [
    ("DOI: 10.1111/abc.123.", "10.1111/abc.123"), ("https://doi.org/10.1007/s11056-013-9373-9,", "10.1007/s11056-013-9373-9"),
    ("(doi:10.1139/S07-038);", "10.1139/S07-038"), ("**10.1016/j.foreco.2019.117839**", "10.1016/j.foreco.2019.117839"),
    ("<https://doi.org/10.1093/foo/bar>", "10.1093/foo/bar"), ("see [link](https://doi.org/10.1000/x.y) here", "10.1000/x.y"),
])
def test_wrapping_and_trailing_punctuation_are_stripped(line, expected):
    assert doimod.find_doi([line])[0] == expected


def test_matches_in_the_first_15_lines_are_preferred_and_reference_lines_skipped():
    lines = ["title"] * 2 + ["doi: 10.1111/early.1"] + ["x"] * 26 + ["doi: 10.2222/late.2"]
    assert doimod.find_doi(lines) == ("10.1111/early.1", 3)
    late_only = ["x"] * 20 + ["doi: 10.2222/late.2"]
    assert doimod.find_doi(late_only) == ("10.2222/late.2", 21)
    assert doimod.find_doi(["x"] * 41 + ["doi: 10.2222/too.late.2"])[0] is None          # beyond the first 40 lines
    assert doimod.find_doi(["- Smith, J. 2001. A paper. doi:10.3333/ref.1"])[0] is None   # reference-list line


def test_merge_uses_the_recovered_doi_and_the_run_writes_the_report(monkeypatch, tmp_path):
    row = {"slug": "S", "doi": "", "title": "t", "authors": "A, B", "year": "2000", "journal": "J"}
    assert "doi" not in source_document(row) and source_document(row, "10.1/x")["doi"] == "10.1/x"
    assert source_document({**row, "doi": "10.9/idx"})["doi"] == "10.9/idx"
    m = _patch_client(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert m.run(ROOT / "corpus", out, docs=["4CB9X9XE"], use_cache=False) == 0
    rep = list(csv.DictReader(open(out / "doi_report.csv", encoding="utf-8")))
    assert list(rep[0]) == ["slug", "doi", "source", "line_number"] and len(rep) == 308
    assert {r["source"] for r in rep} == {"index", "none"}                               # nothing recoverable in this corpus
    g = json.loads((out / "camo_graph.json").read_text(encoding="utf-8"))
    assert sum(1 for d in g["source_documents"] if d.get("doi")) == 285


# =================================================================================== --smoke against a mock endpoint
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

KEY = "mock-secret-key-123"


class _Mock:
    def __init__(self, reject_kwargs=False, think=False):
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                outer.requests.append(body)
                if outer_reject and "chat_template_kwargs" in body:
                    return self._send(400, {"error": {"message": "extra field chat_template_kwargs not permitted"}})
                user = body["messages"][1]["content"]
                nums = [int(x) for x in re.findall(r"^\[(\d+)\] ", user, re.M)]
                lines = [f"F|{n}|T1/density/+|c|T2/cover/-|D|exp" for n in nums[:3]] + [f"N|{nums[3]}|T1/density/+|c|T2/height|exp", "F|garbage"]
                text = ("<think>let me think</think>\n" if outer_think else "") + "\n".join(lines)
                self._send(200, {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1234, "completion_tokens": 56}})

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        outer_reject, outer_think = reject_kwargs, think
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def mock_env(monkeypatch):
    made = []

    def make(**kw):
        m = _Mock(**kw)
        made.append(m)
        monkeypatch.setenv("BRINE_URL", f"http://127.0.0.1:{m.port}/v1")
        monkeypatch.setenv("BRINE_MODEL", "mock-model")
        monkeypatch.setenv("BRINE_API_KEY", KEY)
        return m
    yield make
    for m in made:
        m.close()


def smoke(tmp_path, capsys):
    import pipeline.main as m
    rc = m.main(["--smoke", "4CB9X9XE", "--smoke-dir", str(tmp_path / "dev_out")])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_smoke_reports_everything_and_saves_both_files(mock_env, tmp_path, capsys):
    srv = mock_env()
    rc, out, err = smoke(tmp_path, capsys)
    assert rc == 0, err
    assert "endpoint host: 127.0.0.1" in out and "model: mock-model" in out and "thinking: off" in out
    assert "BRINE_URL set, BRINE_MODEL set, BRINE_API_KEY set" in out
    assert "thinking-off parameter: accepted" in out and "<think> block returned: no" in out
    assert "tokens: prompt 1,234, completion 56" in out and "completion tokens per second:" in out and "seconds:" in out
    assert "lines parsed: 3 F + 1 N; unparseable: 1" in out
    assert "validation:" in out and "OK, no errors" in out
    d = tmp_path / "dev_out"
    assert (d / "smoke_4CB9X9XE.txt").read_text().count("\n") >= 4
    import yaml
    g = yaml.safe_load((d / "smoke_4CB9X9XE.yaml").read_text(encoding="utf-8"))
    assert [x["document_id"] for x in g["source_documents"]] == ["4CB9X9XE"] and g["edges"] and validate_graph(g) is None
    assert len(srv.requests) == 1 and srv.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert KEY not in out and KEY not in err and KEY not in (d / "smoke_4CB9X9XE.yaml").read_text()


def test_smoke_reports_the_no_think_fallback(mock_env, tmp_path, capsys):
    srv = mock_env(reject_kwargs=True)
    rc, out, err = smoke(tmp_path, capsys)
    assert rc == 0, err
    assert "REJECTED, fell back to /no_think" in out
    assert srv.requests[-1]["messages"][1]["content"].startswith("/no_think\n") and "chat_template_kwargs" not in srv.requests[-1]


def test_smoke_reports_a_think_block_and_keeps_the_raw_reply(mock_env, tmp_path, capsys):
    mock_env(think=True)
    rc, out, err = smoke(tmp_path, capsys)
    assert rc == 0, err
    assert "<think> block returned: YES" in out and "lines parsed: 3 F + 1 N" in out
    assert "<think>let me think</think>" in (tmp_path / "dev_out" / "smoke_4CB9X9XE.txt").read_text()


def test_smoke_bypasses_the_cache(mock_env, tmp_path, capsys):
    srv = mock_env()
    smoke(tmp_path, capsys)
    smoke(tmp_path, capsys)
    assert len(srv.requests) == 2


def test_smoke_with_missing_environment_exits_2_and_names_only_the_missing_ones(monkeypatch, tmp_path, capsys):
    for v in ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("BRINE_API_KEY", KEY)
    rc, out, err = smoke(tmp_path, capsys)
    assert rc == 2
    assert "BRINE_URL MISSING" in out and "BRINE_MODEL MISSING" in out and "BRINE_API_KEY set" in out
    assert "BRINE_URL" in err and "BRINE_MODEL" in err and KEY not in out and KEY not in err
    assert not (tmp_path / "dev_out").exists()


def test_smoke_on_an_unknown_slug_is_a_clear_error(mock_env, tmp_path, capsys):
    mock_env()
    import pipeline.main as m
    assert m.main(["--smoke", "NOPE1234", "--smoke-dir", str(tmp_path / "o")]) == 2
    assert "not in index.csv" in capsys.readouterr().err


# =================================================================================== streaming client: SSE, idle + total timeouts, retries.csv
import time as _time


class _StreamMock:
    """mode: sse | json | reject_usage | reject_stream | idle | endless"""
    def __init__(self, mode="sse", text="F|1|T1/a/+|c|T2/b/-|D|exp", usage=True):
        self.mode, self.text, self.usage, self.bodies = mode, text, usage, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                outer.bodies.append(body)
                m = outer.mode
                if m == "reject_usage" and "stream_options" in body:
                    return self._json(400, {"error": {"message": "stream_options is not supported"}})
                if m == "reject_stream" and body.get("stream"):
                    return self._json(400, {"error": {"message": "stream not supported"}})
                if m == "json" or not body.get("stream"):
                    return self._json(200, {"choices": [{"message": {"content": outer.text}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    if m == "idle":
                        self._chunk("F|1|")
                        _time.sleep(2.0)
                        return
                    if m == "endless":
                        while True:
                            self._chunk("x")
                            _time.sleep(0.05)
                    self.wfile.write(b": keep-alive\n\n")
                    for piece in [outer.text[i:i + 7] for i in range(0, len(outer.text), 7)]:
                        self._chunk(piece)
                    if outer.usage and body.get("stream_options", {}).get("include_usage"):
                        self.wfile.write(("data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 22}}) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _chunk(self, s):
                self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": s}}]}) + "\n\n").encode())
                self.wfile.flush()

            def _json(self, code, obj):
                d = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d)))
                self.end_headers()
                self.wfile.write(d)

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def stream_server():
    made = []

    def make(**kw):
        m = _StreamMock(**kw)
        made.append(m)
        return m
    yield make
    for m in made:
        m.close()


def scfg(tmp_path, url, **kw):
    return LLMConfig(url=url, model="m", key=KEY, cache_dir=tmp_path / "cache", use_cache=False, **kw)


def test_defaults_are_120s_idle_and_1200s_total():
    c = LLMConfig(url="u", model="m", key="k")
    assert (c.idle_timeout, c.total_timeout) == (120.0, 1200.0)


def test_streamed_reply_is_assembled_and_usage_taken_from_the_final_chunk(stream_server, tmp_path):
    srv = stream_server(text="<think>x</think>F|12|T1/density/+|c|T2/cover/-|D|exp|stage=seedling")
    r = Client(scfg(tmp_path, srv.url), sleep=lambda s: None).complete("sys", "user", "DOC1")
    assert r.text == "F|12|T1/density/+|c|T2/cover/-|D|exp|stage=seedling" and r.think_returned
    assert (r.prompt_tokens, r.completion_tokens) == (11, 22)
    b = srv.bodies[0]
    assert b["stream"] is True and b["stream_options"] == {"include_usage": True} and b["chat_template_kwargs"] == {"enable_thinking": False}


def test_server_that_ignores_stream_returns_plain_json_and_still_works(stream_server, tmp_path):
    srv = stream_server(mode="json", text="F|1|a")
    r = Client(scfg(tmp_path, srv.url), sleep=lambda s: None).complete("s", "u")
    assert r.text == "F|1|a" and (r.prompt_tokens, r.completion_tokens) == (7, 3)


def test_stream_options_rejected_then_stream_rejected_degrades_step_by_step(stream_server, tmp_path):
    srv = stream_server(mode="reject_usage")
    c = Client(scfg(tmp_path, srv.url), sleep=lambda s: None)
    r = c.complete("s", "u")
    assert r.text.startswith("F|1|") and c._stream == "nousage" and "stream_options" not in srv.bodies[-1]
    assert srv.bodies[-1]["stream"] is True and r.completion_tokens > 0                      # no usage chunk: estimated, not zero
    srv2 = stream_server(mode="reject_stream")
    c2 = Client(scfg(tmp_path, srv2.url), sleep=lambda s: None)
    r2 = c2.complete("s", "u")
    assert c2._stream == "off" and "stream" not in srv2.bodies[-1] and r2.text == "F|1|T1/a/+|c|T2/b/-|D|exp"


def test_idle_timeout_retries_and_writes_retries_csv(stream_server, tmp_path):
    srv = stream_server(mode="idle")
    log_path = tmp_path / "out" / "retries.csv"
    sleeps = []
    c = Client(scfg(tmp_path, srv.url, idle_timeout=0.4, retries=2), sleep=sleeps.append, retry_log=log_path)
    with pytest.raises(LLMError, match="3 attempts"):
        c.complete("s", "u", "DOC9")
    rows = list(csv.DictReader(open(log_path, encoding="utf-8")))
    assert [r["attempt"] for r in rows] == ["1", "2", "3"] and {r["doc"] for r in rows} == {"DOC9"}
    assert "timed out" in rows[0]["error"].lower() and [r["gave_up"] for r in rows] == ["0", "0", "1"] and sleeps == [2, 4]
    assert srv.bodies and srv.bodies[0]["stream"] is True


def test_total_timeout_cuts_a_stream_that_never_ends(stream_server, tmp_path):
    srv = stream_server(mode="endless")
    log_path = tmp_path / "retries.csv"
    c = Client(scfg(tmp_path, srv.url, idle_timeout=5, total_timeout=0.6, retries=1), sleep=lambda s: None, retry_log=log_path)
    t0 = _time.time()
    with pytest.raises(LLMError):
        c.complete("s", "u", "DOC2")
    assert _time.time() - t0 < 6
    rows = list(csv.DictReader(open(log_path, encoding="utf-8")))
    assert len(rows) == 2 and "total timeout" in rows[0]["error"]


def test_retry_log_exists_with_a_header_even_when_nothing_was_retried(tmp_path):
    p = tmp_path / "o" / "retries.csv"
    Client(cfg(tmp_path), retry_log=p).init_retry_log()
    assert p.read_text().strip() == "timestamp,doc,attempt,error,sleep_s,gave_up"


def test_5xx_retry_is_logged_with_the_doc_label(tmp_path):
    p = tmp_path / "retries.csv"
    script = [(503, {}), reply("ok")]
    c = Client(cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=lambda u, pl: script.pop(0), retry_log=p)
    c.complete("s", "u", "SLUG1")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["doc"] == "SLUG1" and rows[0]["error"] == "HTTP 503" and rows[0]["gave_up"] == "0"


def test_a_run_creates_output_retries_csv(monkeypatch, tmp_path):
    m = _patch_client(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert m.run(ROOT / "corpus", out, docs=["4CB9X9XE"], use_cache=False) == 0
    assert (out / "retries.csv").read_text().splitlines()[0] == "timestamp,doc,attempt,error,sleep_s,gave_up"
