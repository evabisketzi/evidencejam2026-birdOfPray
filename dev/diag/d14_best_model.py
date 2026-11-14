"""Score every finished job in dev/jobs/out on the gold papers it covered; group by variant; mean (min-max)."""
import sys, re, json, statistics as st, collections; sys.path.insert(0, "dev")
from eval_murphy import *
from dev.score.load import load_graph
from dev.score.metrics import score
GOLDS = [("murphy2005", GOLD, "murphy2005", SLUG)] + [(s, p, g, s) for s, p, g in OTHER]
groups = collections.defaultdict(list)
for d in sorted((ROOT / "dev/jobs/out").iterdir()):
    if not d.is_dir() or not (d / "camo_graph.yaml").exists() or not re.search(r"_r\d$", d.name): continue
    pred = load_graph(d / "camo_graph.yaml").edges_by_doc
    tp = {"standard": 0, "strict": 0, "loose": 0}; ng = npr = 0; gn = mn = 0; per = {}
    for name, gp, gid, slug in GOLDS:
        if slug not in pred: continue
        gold = load_graph(gp, gid); key = next(iter(gold.edges_by_doc))
        s = score(gold.edges_by_doc, {}, {slug: pred[slug]}, {key: slug})["modes"]["raw"]["docs"][key]
        for lv in tp: tp[lv] += s["levels"][lv]["tp"]
        ng += s["n_gold"]; npr += s["n_pred"]; gn += s["null"]["gold_null"]; mn += s["null"]["matched"]
        per[name] = s["levels"]["standard"]["f1"]
    f = lambda t: 2 * t / (ng + npr) if ng + npr else 0
    tok = sum(int(r.split(",")[1]) + int(r.split(",")[2]) for r in open(d / "tokens.csv").read().splitlines()[1:] if r.split(",")[1].isdigit())
    groups[d.name.rsplit("_r", 1)[0]].append({"papers": len(per), "std": f(tp["standard"]), "strict": f(tp["strict"]), "loose": f(tp["loose"]),
                                               "null": mn / gn if gn else 0, "murphy": per.get("murphy2005"), "tokens": tok, **{f"p_{k}": v for k, v in per.items()}})
def c(xs, k, fmt="{:.3f}"):
    v = [x[k] for x in xs if x.get(k) is not None]
    return "—" if not v else (fmt.format(st.mean(v)) + (f" ({fmt.format(min(v))}–{fmt.format(max(v))})" if len(v) > 1 else ""))
names = sorted(groups)
print("| variant (runs, papers) | micro std F1 | strict | loose | null recall | Murphy std F1 | tokens/run |"); print("|---|---:|---:|---:|---:|---:|---:|")
for n in names:
    x = groups[n]; print(f"| {n} ({len(x)}, {x[0]['papers']}) | {c(x,'std')} | {c(x,'strict')} | {c(x,'loose')} | {c(x,'null')} | {c(x,'murphy')} | {c(x,'tokens','{:,.0f}')} |")
print(); papers = sorted({k for g in groups.values() for x in g for k in x if k.startswith("p_")})
print("| variant | " + " | ".join(p[2:] for p in papers) + " |"); print("|---|" + "---:|" * len(papers))
for n in names: print(f"| {n} | " + " | ".join(c(groups[n], p) for p in papers) + " |")
