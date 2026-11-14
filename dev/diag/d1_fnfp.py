import sys, json; sys.path.insert(0, "dev/diag")
from common import *
from dev.score.load import load_graph
from dev.score.match import subject_sim, taxon_component, attr_sim
S = json.load(open(RUN / "dev_baseline/score/score.json"))["score"]["modes"]["raw"]
gold = load_graph(ROOT / "dev/gold/4CB9X9XE.camo.yaml").edges_by_doc["4CB9X9XE"]
pred = load_graph(RUN / "dev_baseline/camo_graph.yaml").edges_by_doc["4CB9X9XE"]
gby = {e.edge_id: e for e in gold}
pby = {e.edge_id: e for e in pred}
fn = [x for x in S["fn"] if x["doc"] == "4CB9X9XE"]; fp = [x for x in S["fp"] if x["doc"] == "4CB9X9XE"]
def sig(s):
    return (f"name={s.name!r} | taxa_ids={sorted(s.taxa_ids) or '-'} taxa_text={sorted('%s.%s'%t for t in s.taxa_text) or '-'} "
            f"| entity_text={sorted(s.entity_text) or '-'} | attr={s.attribute!r} | dir={s.direction}")
def closest(s, nodes, k=3):
    seen = {}
    for n in nodes: seen.setdefault(n.id, n)
    sc = sorted(seen.values(), key=lambda n: -(0.5*taxon_component(s, n) + 0.3*attr_sim(s, n) + 0.2*(s.direction == n.direction) + 0.3*len(s.entity_text & n.entity_text)/max(1, len(s.entity_text | n.entity_text))))
    return sc[:k]
pn = [e.subj for e in pred] + [e.obj for e in pred]
o = ["# 4CB9X9XE baseline (dev_baseline run): false negatives and false positives\n",
     f"gold edges {len(gold)}, predicted edges {len(pred)}, FN {len(fn)}, FP {len(fp)}\n",
     "entity_agree (the loose gate) needs: both nodes have a taxon -> shared NCBITaxon id or shared (genus,epithet); else the free-text entity must have Jaccard >= 0.5.\n",
     "## FALSE NEGATIVES (all)\n"]
for i, x in enumerate(fn, 1):
    o.append(f"{i}. [{x['gold_edge']}] {x['reason']}\n   gold: {x['gold']}\n   best candidate (sim {x['best_sim']}): {x['best_candidate']}\n   sentence: {x['sentence']}")
o.append("\n## FALSE POSITIVES (all)\n")
for i, x in enumerate(fp, 1):
    o.append(f"{i}. [{x['pred_edge']}] {x['reason']}\n   ours: {x['pred']}\n   nearest gold (sim {x['nearest_sim']}): {x['nearest_gold']}\n   sentence: {x['sentence']}")
o.append("\n## FIRST 10 FNs: gold node terms next to the closest predicted nodes\n")
for i, x in enumerate(fn[:10], 1):
    g = gby[x["gold_edge"]]
    o.append(f"### FN {i} [{x['gold_edge']}] {x['gold']}   ({x['reason_code']})")
    for role, gs in (("SUBJECT", g.subj), ("OBJECT", g.obj)):
        o.append(f"  gold {role}: {sig(gs)}")
        for n in closest(gs, pn):
            o.append(f"     closest predicted: {sig(n)}   [entity_agree={'yes' if __import__('dev.score.match',fromlist=['x']).entity_agree(gs, n) else 'no'}]")
    o.append("")
open("dev/diag/1_4CB9X9XE_fn_fp.md", "w").write("\n".join(o))
print("\n".join(o[:4])); print(len(fn), len(fp))
from collections import Counter
print(Counter(x["reason_code"] for x in fn), Counter(x["reason_code"] for x in fp))
