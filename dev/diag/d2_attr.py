import sys, json; sys.path.insert(0, "dev/diag")
from common import *
from dev.score.load import load_graph
from dev.score.match import match_document
from dev.score import metrics as M
gold = load_graph(ROOT / "dev/gold/murphy2005.yaml", "murphy2005").edges_by_doc["murphy2005"]
pred = load_graph(RUN / "dev_baseline/camo_graph.yaml").edges_by_doc["YKQQZV93"]
m = match_document(gold, pred, 0.5)
std = {p.i for p in m.level("standard")}
rows = []
for p in m.pairs:
    if p.i in std: continue
    code, text = M._reason(p, M._null_mismatch(gold[p.i], pred))
    if code != "attribute_differs": continue
    g, q = gold[p.i].obj, pred[p.j].obj
    rows.append((gold[p.i].edge_id, g.attribute, q.attribute, p.obj_attr, sorted(g.attr_tokens), sorted(q.attr_tokens), g.name, q.name, g.qualifier, q.qualifier))
o = ["# Murphy 2005, baseline (dev_baseline): all 'attribute differs' pairs (object attribute, threshold 0.5)\n",
     f"count: {len(rows)}\n",
     "| gold edge | gold attribute | predicted attribute | similarity | gold tokens | predicted tokens | gold object name | predicted object name |", "|---|---|---|---:|---|---|---|---|"]
for r in rows:
    o.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.2f} | {' '.join(r[4])} | {' '.join(r[5])} | {r[6]} | {r[7]} |")
open("dev/diag/2_murphy_attribute_differs.md", "w").write("\n".join(o))
for r in rows: print(f"{r[0]:14} {str(r[1])[:34]:34} | {str(r[2])[:42]:42} | {r[3]:.2f} | {r[4]} vs {r[5]}")
