"""Ontology coverage of a CAMO graph, and what the ontology module (ontology/ground_terms.py) would add.

    python dev/diag/ontology_coverage.py GRAPH.yaml [--docs SLUG,...] [--json OUT]

Per field (entity_term by entity_type, measured_attribute, life_stage_term, applied_to.entity_term):
  values        number of node values
  curie         share that is already a CURIE (by prefix)
  +lookup       share of the free-text values that ground_terms resolves automatically (unique exact label / exact synonym):
                the coverage `--ontology lookup` would add, without any LLM call
  pending       free-text values that would go to the LLM selection step (ambiguous / needs_review)
Existing CURIEs are checked with ground_terms.check_existing: not_found (no such term in the local index) and check_label (the
term's label does not resemble the node name) are listed; taxa are not checked (no NCBITaxon index is committed).
No network, no LLM."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ontology"))

from ground_terms import CAMO_PREFIXES, Prefixes, Registry, ground_graph, load_config  # noqa: E402

FIELDS = ("entity_term", "measured_attribute", "life_stage_term")


def load(p: str) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f) if p.endswith(".json") else yaml.safe_load(f)


def coverage(graph: dict, docs=None, registry: Registry | None = None) -> dict:
    px = Prefixes(CAMO_PREFIXES)
    nodes = graph.get("nodes") or []
    if docs:
        keep = {e["subject"] for e in graph["edges"] if e.get("source_document") in docs}
        keep |= {e["object"] for e in graph["edges"] if e.get("source_document") in docs}
        nodes = [n for n in nodes if n["id"] in keep]
    rows: dict = defaultdict(lambda: {"values": 0, "curie": 0, "prefixes": Counter(), "free": []})
    for n in nodes:
        for fld in FIELDS:
            v = n.get(fld)
            if not isinstance(v, str) or not v.strip():
                continue
            key = f"entity_term [{n.get('entity_type') or 'untyped'}]" if fld == "entity_term" else fld
            r = rows[key]
            r["values"] += 1
            if px.is_curie(v):
                r["curie"] += 1
                r["prefixes"][px.prefix_of(px.to_camo(v))] += 1
            else:
                r["free"].append(v)
        for a in n.get("applied_to") or []:
            v = a.get("entity_term")
            if isinstance(v, str) and v.strip():
                r = rows["applied_to.entity_term"]
                r["values"] += 1
                if px.is_curie(v):
                    r["curie"] += 1
                    r["prefixes"][px.prefix_of(px.to_camo(v))] += 1
                else:
                    r["free"].append(v)
    registry = registry or Registry(load_config(), px)
    report = ground_graph({"nodes": nodes}, registry, kinds=[k for k in load_config()["kinds"] if k != "taxon"], verbose=False)
    status_of = {(g["kind"], m): g["status"] for g in report["terms"] for m in g["mentions"]}
    by_kind = Counter()
    for g in report["terms"]:
        by_kind[g["status"]] += 1
    out = {"fields": {}, "lookup_terms": dict(by_kind),
           "existing_problems": [c for c in report["existing_curies"]
                                 if c.get("status", "").startswith(("not_found", "check_label"))]}
    for key, r in sorted(rows.items()):
        kind = (key.split("[", 1)[1].rstrip("]") if key.startswith("entity_term [") else
                "measured_attribute" if key == "measured_attribute" else "life_stage" if key == "life_stage_term" else None)
        resolved = pending = 0
        for v in r["free"]:
            st = status_of.get((kind, v.strip())) if kind else None
            resolved += st == "resolved"
            pending += st in ("ambiguous", "needs_review")
        out["fields"][key] = {"values": r["values"], "curie": r["curie"], "prefixes": dict(r["prefixes"]),
                              "lookup_resolves": resolved, "lookup_pending": pending}
    return out


def render(cov: dict) -> str:
    lines = ["| field | values | CURIE now | prefixes | + lookup (auto) | to LLM selection |", "|---|---:|---:|---|---:|---:|"]
    tot = Counter()
    for key, r in cov["fields"].items():
        v = max(1, r["values"])
        pre = ", ".join(f"{p} {c}" for p, c in sorted(r["prefixes"].items(), key=lambda x: -x[1])) or "—"
        lines.append(f"| {key} | {r['values']} | {r['curie'] / v:.0%} | {pre} | +{r['lookup_resolves'] / v:.0%} | "
                     f"{r['lookup_pending'] / v:.0%} |")
        for k in ("values", "curie", "lookup_resolves", "lookup_pending"):
            tot[k] += r[k]
    v = max(1, tot["values"])
    lines.append(f"| **all** | {tot['values']} | {tot['curie'] / v:.0%} | | +{tot['lookup_resolves'] / v:.0%} | "
                 f"{tot['lookup_pending'] / v:.0%} |")
    probs = cov["existing_problems"]
    lines.append(f"\nExisting CURIEs flagged by ground_terms.check_existing: {len(probs)}")
    for p in probs[:15]:
        lines.append(f"- {p['curie']} ({p['field']}, node {p.get('node_name')!r}): {p['status']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graph")
    ap.add_argument("--docs", help="only nodes used by edges of these documents (comma-separated)")
    ap.add_argument("--json", help="also write the numbers here")
    a = ap.parse_args(argv)
    cov = coverage(load(a.graph), {d.strip() for d in a.docs.split(",")} if a.docs else None)
    print(render(cov))
    if a.json:
        Path(a.json).write_text(json.dumps(cov, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
