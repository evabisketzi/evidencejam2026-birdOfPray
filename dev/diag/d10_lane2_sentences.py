"""For the zero-overlap papers: do our edges cite the sentences Lane 2's claims come from?  And examples of the same sentence, both sides."""
import sys, json, csv, re; sys.path.insert(0, "dev/diag")
from collections import Counter, defaultdict
from common import *
SP = Path("/tmp/claude-1000/-home-kbuzko-Code-EvidenceJam/f78c8145-a29b-493a-b62b-29bd744228be/scratchpad")
S = json.load(open(SP / "lane2_vs_baseline/score.json"))["score"]["modes"]["raw"]
L2 = json.load(open(SP / "lanes/l2/causal_graph.json")); n2 = {n["id"]: n for n in L2["nodes"]}
dm = {r["gold_doc"]: r["pred_doc"] for r in csv.DictReader(open(SP / "lane2_docmap_all.csv"))}
ours = json.load(open(RUN / "full_baseline/camo_graph.json")); n1 = {n["id"]: n for n in ours["nodes"]}
oe = defaultdict(list)
for e in ours["edges"]: oe[e["source_document"]].append(e)
def grams(t, k=4):
    w = re.findall(r"[a-z0-9]+", (t or "").lower()); return {tuple(w[i:i+k]) for i in range(max(1, len(w)-k+1))}
zero = [d for d, x in S["docs"].items() if x["n_gold"] and x["levels"]["loose"]["tp"] == 0]
same = 0; tot = 0; ex = []; kinds = Counter()
for d in zero:
    slug = dm[d]
    mine = [(grams(e.get("original_sentence")), e) for e in oe[slug]]
    for e in [x for x in L2["edges"] if x["source_document"] == d]:
        tot += 1
        g = grams(e.get("original_sentence", "").replace("...", ""))
        hits = [o for gg, o in mine if g and len(g & gg) / len(g) >= 0.5]
        if hits:
            same += 1
            ex.append((slug, e, hits[0]))
        kinds[n2[e["subject"]].get("entity_type")] += 1
out = [f"# Zero-overlap papers: Lane 2 claims {tot}; claims whose sentence we ALSO cite: {same} ({same/tot:.0%})\n",
       f"Lane 2 subject entity types in these papers: {dict(kinds.most_common())}\n",
       f"Our subject entity types in these papers: {dict(Counter(n1[e['subject']].get('entity_type') for d in zero for e in oe[dm[d]]).most_common())}\n",
       "## Same sentence, both sides (25 random)\n"]
import random; random.seed(3)
for slug, e, o in random.sample(ex, min(25, len(ex))):
    out.append(f"- [{slug}] «{e.get('original_sentence','')[:160]}»\n    LANE2: {n2[e['subject']]['name']} --{e['predicate']}--> {n2[e['object']]['name']}\n    OURS:  {n1[o['subject']]['name']} --{o['predicate']}--> {n1[o['object']]['name']}")
open("dev/diag/10_lane2_same_sentence.md", "w").write("\n".join(out)); print("\n".join(out))
