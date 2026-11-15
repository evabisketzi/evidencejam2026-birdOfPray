"""Merge step: one node per distinct node content (pipeline/dedup.py), edges untouched, source ids kept in node_map."""
import copy
import csv
import random

from pipeline.dedup import canonical_id, content_key, dedupe, near_duplicate_rows, write_reports
from pipeline.guard import final_integrity, merge, validate_graph


def row(slug):
    return {"slug": slug, "doi": f"10.1/{slug}", "title": slug, "authors": "A", "year": "2001", "journal": "J"}


def span(slug, n, text="Restoration raised richness."):
    return {"text": text, "sentence_id": f"{slug}:s{n}", "start_char": n * 100, "end_char": n * 100 + len(text)}


def node(slug, local, name, term, etype="environmental_variable", qual=None, attr=None, applied=None, spans=None):
    n = {"id": f"node:{slug}_{local}", "name": name, "entity_type": etype, "entity_term": term}
    if attr:
        n["measured_attribute"] = attr
    if qual:
        n["state_or_change_qualifier"] = qual
    if applied:
        n["applied_to"] = applied
    n["source_spans"] = spans if spans is not None else [span(slug, 1)]
    return n


def edge(slug, i, subj, obj, n=1, **extra):
    e = {"id": f"{slug}-e{i}", "source_document": slug, "subject": f"node:{slug}_{subj}", "predicate": "causes",
         "object": f"node:{slug}_{obj}", "causal_language": "direct_causal", "philosophical_accounts": ["counterfactual"],
         "original_sentence": f"sentence {n}", "source_spans": [span(slug, n)]}
    e.update(extra)
    return e


def paper(slug, extra_nodes=(), extra_edges=()):
    nodes = [node(slug, "r", "Restoration", "restoration", etype="management_intervention"),
             node(slug, "s", "Increased species richness", "plant", qual="increased", attr="species richness",
                  spans=[span(slug, 2)])]
    nodes += list(extra_nodes)
    edges = [edge(slug, 1, "r", "s")] + list(extra_edges)
    return slug, {n["id"]: n for n in nodes}, edges


def test_same_node_in_two_papers_becomes_one_shared_node_and_edges_stay_per_paper():
    docs = [paper("AAA"), paper("BBB")]
    nodes, edges, nmap, stats = dedupe(docs)
    assert len(nodes) == 2 and len(edges) == 2
    resto = next(n for n in nodes if n["name"] == "Restoration")
    assert all(e["subject"] == resto["id"] for e in edges)
    assert [e["id"] for e in edges] == ["AAA-e1", "BBB-e1"] and [e["source_document"] for e in edges] == ["AAA", "BBB"]
    assert {s["sentence_id"] for s in resto["source_spans"]} == {"AAA:s1", "BBB:s1"}   # each span still names its paper
    assert stats["node groups shared by several papers"] == 2 and resto["variable_key"] == "restoration||"


def test_same_content_twice_inside_one_paper_is_merged_and_the_now_identical_claim_dropped():
    slug, nodes, edges = paper("AAA", extra_nodes=[node("AAA", "r2", "Restoration", "Restoration ", etype="management_intervention")],
                               extra_edges=[edge("AAA", 2, "r2", "s")])               # same claim, same sentence, other node id
    out_nodes, out_edges, nmap, stats = dedupe([(slug, nodes, edges)])
    assert len(out_nodes) == 2 and [e["id"] for e in out_edges] == ["AAA-e1"]
    assert stats["dropped edge: same claim, same sentence (after node merge)"] == 1
    assert {r["method"] for r in nmap if r["source_node_id"] in ("node:AAA_r", "node:AAA_r2")} == {"exact_content"}


def test_different_content_is_never_merged():
    variants = [node("AAA", "q", "Decreased species richness", "plant", qual="decreased", attr="species richness"),
                node("AAA", "a", "Increased species richness", "plant", qual="increased", attr="species richness",
                     applied=[{"entity_type": "taxon", "entity_term": "NCBITaxon:3472"}]),
                node("AAA", "c", "Increased species richness", "ENVO:01000001", qual="increased", attr="species richness"),
                dict(node("AAA", "l", "Increased species richness", "plant", qual="increased", attr="species richness"),
                     life_stage="seedling")]
    slug, nodes, edges = paper("AAA", extra_nodes=variants, extra_edges=[edge("AAA", i + 2, "r", v["id"].split("_")[-1], n=i + 3)
                                                                       for i, v in enumerate(variants)])
    out_nodes, _, _, stats = dedupe([(slug, nodes, edges)])
    assert len(out_nodes) == len(nodes) and stats["nodes merged away"] == 0


def test_every_node_reference_is_rewritten():
    m = node("AAA", "m", "Soil moisture", "soil moisture")
    e = edge("AAA", 2, "r", "s", n=5, mediation={"mediator_node_ids": ["node:AAA_m"], "status": "explicitly_asserted"},
             moderation={"moderator_node_ids": ["node:AAA_m"]},
             comparator=[{"comparator_type": "alternative_treatment", "comparator_node_id": "node:AAA_m"}])
    nodes, edges, _, _ = dedupe([paper("AAA", extra_nodes=[m], extra_edges=[e])])
    ids = {n["id"] for n in nodes}
    e2 = edges[1]
    refs = [e2["subject"], e2["object"], *e2["mediation"]["mediator_node_ids"], *e2["moderation"]["moderator_node_ids"],
            e2["comparator"][0]["comparator_node_id"]]
    assert all(r in ids for r in refs)
    assert e["mediation"]["mediator_node_ids"] == ["node:AAA_m"]                   # the input edge is not modified


def test_invariants_source_ids_and_documents_are_kept():
    docs = [paper("AAA"), paper("BBB"), paper("CCC", extra_nodes=[node("CCC", "x", "Fire", "fire")],
                                                 extra_edges=[edge("CCC", 2, "x", "s", n=3)])]
    in_nodes = [(slug, nid) for slug, ns, _ in docs for nid in ns]
    in_edges = [e["id"] for _, _, es in docs for e in es]
    nodes, edges, nmap, _ = dedupe(docs)
    assert sorted((r["document_id"], r["source_node_id"]) for r in nmap) == sorted(in_nodes)        # I3: each exactly once
    assert sorted(e["id"] for e in edges) == sorted(in_edges)                                          # I4
    ids = {n["id"] for n in nodes}
    assert {r["canonical_node_id"] for r in nmap} == ids
    for n in nodes:                                                                                    # I5
        docs_of_members = {r["document_id"] for r in nmap if r["canonical_node_id"] == n["id"]}
        assert {s["sentence_id"].split(":s")[0] for s in n["source_spans"]} == docs_of_members
    assert {r["document_id"] for r in nmap} == {"AAA", "BBB", "CCC"}                                   # I7


def test_canonical_ids_and_spans_do_not_depend_on_paper_order():
    docs = [paper("AAA"), paper("BBB"), paper("CCC")]
    a, _, _, _ = dedupe(docs)
    shuffled = copy.deepcopy(docs)
    random.Random(1).shuffle(shuffled)
    b, _, _, _ = dedupe(shuffled)
    key = lambda ns: sorted((n["id"], n["name"], tuple(s["sentence_id"] for s in n["source_spans"])) for n in ns)
    assert key(a) == key(b)
    assert canonical_id(content_key(docs[0][1]["node:AAA_r"])) in {n["id"] for n in a}


def test_merged_graph_validates_and_has_no_duplicate_content(tmp_path):
    docs = [paper("AAA"), paper("BBB")]
    nmap = []
    g = merge([row("AAA"), row("BBB")], {s: (n, e) for s, n, e in docs}, node_map=nmap)
    assert validate_graph(g) is None and final_integrity(g) == []
    assert len(g["nodes"]) == 2 and len(nmap) == 4
    g["nodes"].append(dict(g["nodes"][0], id="node:other"))
    assert any("same content" in p for p in final_integrity(g))
    write_reports(tmp_path, g["nodes"][:2], nmap)
    with open(tmp_path / "merged_nodes.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert all(r["n_documents"] == "2" and r["source_document_ids"] == "AAA|BBB" for r in rows)
    assert (tmp_path / "node_map.csv").exists() and (tmp_path / "near_duplicates.csv").exists()


def test_same_curie_under_another_name_is_reported_not_merged():
    """The scorer reads the entity from the name when entity_term is a CURIE: a merge must never rename a paper's node."""
    a = node("AAA", "1", "Grazing", "ENVO:01001200", etype="management_intervention")
    b = node("BBB", "1", "Livestock grazing", "ENVO:01001200", etype="management_intervention")
    nodes, _, _, _ = dedupe([("AAA", {a["id"]: a}, []), ("BBB", {b["id"]: b}, [])])
    assert sorted(n["name"] for n in nodes) == ["Grazing", "Livestock grazing"]
    rows = near_duplicate_rows(nodes)
    assert len(rows) == 1 and rows[0]["reason_not_merged"].startswith("same content, different name")


def test_near_duplicates_are_reported_not_merged():
    a = node("AAA", "1", "Seedlings", "seedlings")
    b = node("BBB", "1", "Seedling", "seedling")
    nodes, _, _, _ = dedupe([("AAA", {a["id"]: a}, []), ("BBB", {b["id"]: b}, [])])
    assert len(nodes) == 2
    rows = near_duplicate_rows(nodes)
    assert len(rows) == 1 and {rows[0]["name_a"], rows[0]["name_b"]} == {"Seedlings", "Seedling"}
