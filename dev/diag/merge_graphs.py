"""Merge per-paper CAMO graphs (one YAML/JSON file per paper, e.g. camo_pipeline/out/graphs/) into one CausalGraph, so the
team scorer (dev/eval_murphy.py, dev/results_table.py) can score them like a pipeline run.

    python dev/diag/merge_graphs.py OUT.yaml GRAPH [GRAPH ...]        (GRAPH: files or directories; .yaml preferred over .json)

Nodes, edges and source_documents are concatenated; a repeated id is a hard error (ids are per paper, so it means the same
paper was given twice).  Only for evaluation: the submission graph comes from pipeline.main."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def graph_files(args):
    for a in args:
        p = Path(a)
        if p.is_dir():
            ys = sorted(p.glob("*.yaml"))
            stems = {y.stem for y in ys}
            yield from ys
            yield from (j for j in sorted(p.glob("*.json")) if j.stem not in stems)
        else:
            yield p


def load(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f) if p.suffix == ".json" else yaml.safe_load(f)


def merge(files) -> dict:
    out = {"graph_id": "merged_for_evaluation", "schema_version": None, "provenance": {}, "source_documents": [],
           "nodes": [], "edges": []}
    seen = {"source_documents": set(), "nodes": set(), "edges": set()}
    for p in files:
        g = load(p)
        out["schema_version"] = out["schema_version"] or g.get("schema_version")
        out["provenance"] = out["provenance"] or g.get("provenance") or {}
        for key, idk in (("source_documents", "document_id"), ("nodes", "id"), ("edges", "id")):
            for item in g.get(key) or []:
                if item[idk] in seen[key]:
                    raise SystemExit(f"{p}: {key} id {item[idk]!r} appears twice")
                seen[key].add(item[idk])
                out[key].append(item)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    g = merge(graph_files(argv[1:]))
    with open(argv[0], "w", encoding="utf-8") as f:
        yaml.safe_dump(g, f, sort_keys=False, allow_unicode=True, width=4096)
    print(f"{argv[0]}: {len(g['source_documents'])} documents, {len(g['nodes'])} nodes, {len(g['edges'])} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
