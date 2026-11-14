"""Make a deliberately weakened prediction from a gold file (for sanity-checking the scorer).

    python -m dev.score.weaken dev/gold/murphy2005.yaml murphy2005 dev/score_out/weak_murphy_pred.yaml

Steps: flatten the wrapper into one CausalGraph (node/edge ids prefixed per finding, so ids differ from the gold),
delete a third of the edges, shuffle the measured attributes across nodes, flip one null result to a positive edge.
"""
from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

import yaml


def wrapper_to_graph(path, doc_id: str) -> dict:
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    nodes, edges = [], []
    for item in d["graphs"]:
        fid = str(item["finding_id"])
        pre = lambda x: f"{fid}:{x}"
        g = copy.deepcopy(item["graph"])
        for n in g["nodes"]:
            n["id"] = pre(n["id"])
            nodes.append(n)
        for e in g["edges"]:
            e["id"] = pre(e["id"])
            e["subject"], e["object"] = pre(e["subject"]), pre(e["object"])
            for blk, key in (("mediation", "mediator_node_ids"), ("moderation", "moderator_node_ids")):
                if e.get(blk) and e[blk].get(key):
                    e[blk][key] = [pre(x) for x in e[blk][key]]
            e["source_document"] = doc_id
            e.setdefault("original_sentence", item.get("sentence"))
            edges.append(e)
    return {"graph_id": f"weak:{doc_id}", "schema_version": "0.10.0", "provenance": {"project": "dev scorer test"},
            "source_documents": [{"document_id": doc_id}], "nodes": nodes, "edges": edges}


def weaken(graph: dict, seed: int = 7) -> tuple:
    rng = random.Random(seed)
    g = copy.deepcopy(graph)
    log = {"edges_before": len(g["edges"])}
    k = len(g["edges"]) // 3
    drop = set(rng.sample(range(len(g["edges"])), k))
    g["edges"] = [e for i, e in enumerate(g["edges"]) if i not in drop]
    log["edges_deleted"] = k
    attrs = [n.get("measured_attribute") for n in g["nodes"]]
    rng.shuffle(attrs)
    for n, a in zip(g["nodes"], attrs):
        if a is None:
            n.pop("measured_attribute", None)
        else:
            n["measured_attribute"] = a
    log["attributes_shuffled"] = len(attrs)
    nulls = [e for e in g["edges"] if e.get("negated") or e.get("causal_language") == "no_relationship"]
    if nulls:
        e = nulls[0]
        e["negated"] = False
        e["causal_language"] = "direct_causal"
        log["null_flipped"] = e["id"]
    return g, log


if __name__ == "__main__":
    src, doc, dst = sys.argv[1:4]
    g, log = weaken(wrapper_to_graph(src, doc))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(yaml.safe_dump(g, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    print(log)
