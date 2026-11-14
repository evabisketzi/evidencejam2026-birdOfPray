"""Recall ceiling: is the sentence a gold edge cites visible to the model? Fuzzy (word 4-gram overlap >= 0.6), because the Murphy gold sentences come from the PDF."""
import sys, csv, re; sys.path.insert(0, "dev/diag")
from common import *
from pipeline.preprocess.team_adapter import process_paper_team
from dev.score.load import load_graph
count, _ = get_counter(allow_download=False); table = load_taxon_table()
rows = list(csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8")))
def grams(t, k=4):
    w = re.findall(r"[a-z0-9]+", (t or "").lower()); return {tuple(w[i:i+k]) for i in range(max(1, len(w)-k+1))}
o = ["# Recall ceiling per preprocessing (gold edges whose cited sentence is visible to the model; fuzzy 4-gram overlap >= 0.6)\n"]
for gp, gid, slug in (("dev/gold/murphy2005.yaml", "murphy2005", "YKQQZV93"), ("dev/gold/4CB9X9XE.camo.yaml", None, "4CB9X9XE")):
    g = load_graph(ROOT / gp, gid); key = next(iter(g.edges_by_doc)); gold = g.edges_by_doc[key]
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace"); meta = next(r for r in rows if r["slug"] == slug)
    miss = {}
    for name, fn in (("ours", process_paper), ("team", process_paper_team)):
        pre = fn(slug, raw, meta, count, Options(), table)
        G = set().union(*(grams(s["clean"]) for s in pre.sidecar["sentences"]))
        ok = 0; missed = []
        for e in gold:
            gg = grams(e.sentences[0]) if e.sentences else set()
            f = len(gg & G) / len(gg) if gg else 0
            if f >= 0.6: ok += 1
            else: missed.append(e.sentences[0][:110] if e.sentences else "?")
        miss[name] = missed
        o.append(f"- {key} / {name}: {ok}/{len(gold)} gold edges visible ({ok/len(gold):.0%}); sentences {len(pre.sidecar['sentences'])}, tokens {count(pre.txt)}")
    only_ours = set(miss["team"]) - set(miss["ours"]); only_team = set(miss["ours"]) - set(miss["team"])
    o.append(f"  visible only with ours: {len(only_ours)}; visible only with team: {len(only_team)}")
    for t in list(only_ours)[:3]: o.append(f"    lost by team: {t}")
    for t in list(only_team)[:3]: o.append(f"    gained by team: {t}")
open("dev/diag/6_recall_ceiling.md", "w").write("\n".join(o)); print("\n".join(o))
