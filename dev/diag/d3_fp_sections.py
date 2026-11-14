import sys, json, random; sys.path.insert(0, "dev/diag")
from collections import Counter
from common import *
from dev.score.load import load_graph
S = json.load(open(RUN / "dev_baseline/score/score.json"))["score"]["modes"]["raw"]
pred = load_graph(RUN / "dev_baseline/camo_graph.yaml").edges_by_doc
docs = {"4CB9X9XE": "4CB9X9XE", "murphy2005": "YKQQZV93"}
o = ["# False positives with reason 'no loose match', both papers (dev_baseline)\n"]
allrows = []
for gd, slug in docs.items():
    pre = pre_for(slug)
    sents = {s["start_char"]: s for s in pre.sidecar["sentences"]}
    by_start = sorted(pre.sidecar["sentences"], key=lambda s: s["start_char"])
    def find(spans):
        for a, b, _ in spans or ():
            if a in sents: return sents[a]
            for s in by_start:
                if a is not None and s["start_char"] <= a < s["end_char"]: return s
        return None
    pe = {e.edge_id: e for e in pred[slug]}
    base = Counter(find(e.spans)["section"] if find(e.spans) else "?" for e in pred[slug])
    fps = [x for x in S["fp"] if x["doc"] == ("murphy2005" if gd == "murphy2005" else gd)]
    nl = [x for x in fps if x["reason_code"] == "no_loose_match"]
    cnt = Counter()
    for x in nl:
        s = find(pe[x["pred_edge"]].spans)
        sec = s["section"] if s else "?"
        cnt[sec] += 1
        allrows.append((gd, sec, x, s))
    sentcnt = Counter(s["section"] for s in pre.sidecar["sentences"])
    o += [f"## {gd} (corpus {slug})", f"- predicted edges {len(pe)}, false positives {len(fps)}, of which no loose match {len(nl)}",
          f"- no-loose-match FPs by section of the cited sentence: {dict(cnt)}",
          f"- all predicted edges by section: {dict(base)}",
          f"- sentences given to the model by section: {dict(sentcnt)}\n"]
tot = Counter(r[1] for r in allrows)
o += [f"## Both papers together: {len(allrows)} no-loose-match FPs by section: {dict(tot)}\n", "## 15 random examples (seed 7)\n"]
random.seed(7)
for i, (gd, sec, x, s) in enumerate(random.sample(allrows, 15), 1):
    o.append(f"{i}. [{gd} {x['pred_edge']}] section={sec} sentence n={s['n'] if s else '?'}\n   ours: {x['pred']}\n   nearest gold (sim {x['nearest_sim']}): {x['nearest_gold']}\n   text: {s['raw'] if s else x['sentence']}")
open("dev/diag/3_fp_no_loose_match_sections.md", "w").write("\n".join(o))
print("\n".join(o[:22]))
