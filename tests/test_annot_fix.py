"""dev/annot_fix.py: mechanical clean-up of a machine-made annotation."""
from dev.annot_fix import fix, strip_brackets

RAW = "Intro text.\n\nBlue rings were associated with cool temperatures (R <sup>2</sup> = 0.17, see [Figure 4](#page-8-0)). More text."


def test_spans_get_offsets_into_the_raw_markdown_and_terms_are_cleaned():
    g = {"nodes": [{"id": "n1", "entity_type": "management_intervention",
                    "entity_term": "black plastic mulch (1.8 m wide) over planting rows", "measured_attribute": "cover (percent)",
                    "source_spans": [{"text": "Blue rings were associated with cool temperatures (R2 = 0.17, see Figure 4)."}]},
                   {"id": "n2", "entity_type": "taxon", "entity_term": "Poa pratensis", "source_spans": [{"text": "not in the paper"}]}],
         "edges": [{"id": "e1", "subject": "n1", "predicate": "causes", "object": "n2", "original_sentence": "s"},
                   {"id": "e2", "subject": "n1", "predicate": "causes", "object": "n2", "original_sentence": "s"}]}
    rep = fix(g, RAW, [("entity_term", "black plastic mulch over planting rows", "black plastic mulch")])
    sp = g["nodes"][0]["source_spans"][0]
    assert RAW[sp["start_char"]:sp["end_char"]] == sp["text"] and sp["text"].startswith("Blue rings") and sp["text"].endswith(").")
    assert g["nodes"][0]["entity_term"] == "black plastic mulch" and g["nodes"][0]["measured_attribute"] == "cover"
    assert g["nodes"][1]["entity_term"] == "NCBITaxon:4545"
    assert "start_char" not in g["nodes"][1]["source_spans"][0] and len(rep["spans not found"]) == 1
    assert [e["id"] for e in g["edges"]] == ["e1"] and rep["duplicate edges dropped"] == ["e2"]


def test_strip_brackets_never_returns_an_empty_term():
    assert strip_brackets("(only a note)") == "(only a note)"
    assert strip_brackets("root egress (egressed mass / total mass)") == "root egress"
