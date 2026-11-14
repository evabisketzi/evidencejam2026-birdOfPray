"""Gold edges that NO run found (8 runs: 2 prompts on the sentence filter, 3 repeats each of sentence filter and paragraph selection)."""
import sys, re, csv, json; sys.path.insert(0, "dev/diag")
from collections import Counter, defaultdict
from common import *
from dev.score.load import load_graph
from dev.score.match import match_document
from dev.score import metrics as M
from pipeline.preprocess.team_adapter import process_paper_team
runs = {"baseline": RUN/"dev_baseline", "socratic": RUN/"dev_socratic"}
for v in ("ours", "team"):
    for r in (1, 2, 3): runs[f"{v}_{r}"] = ROOT/f"dev/preproc_compare/20261114_105939/{v}_{r}"
count, _ = get_counter(allow_download=False); table = load_taxon_table(); rows = list(csv.DictReader(open(ROOT/"corpus/index.csv", encoding="utf-8")))
def grams(t, k=4):
    w = re.findall(r"[a-z0-9]+", (t or "").lower()); return {tuple(w[i:i+k]) for i in range(max(1, len(w)-k+1))}
out = ["# Gold edges missed by every run (8 runs), and why\n"]; summary = {}
for gp, gid, slug in (("dev/gold/murphy2005.yaml", "murphy2005", "YKQQZV93"), ("dev/gold/4CB9X9XE.camo.yaml", None, "4CB9X9XE")):
    g = load_graph(ROOT/gp, gid); key = next(iter(g.edges_by_doc)); gold = g.edges_by_doc[key]
    found = defaultdict(int); reasons = defaultdict(Counter)
    for name, d in runs.items():
        P = load_graph(d/"camo_graph.yaml").edges_by_doc.get(slug, [])
        m = match_document(gold, P, 0.5); std = {p.i for p in m.level("standard")}
        by_g = {p.i: p for p in m.pairs}
        for i, e in enumerate(gold):
            if i in std: found[i] += 1
            else:
                lp = by_g.get(i); code, _ = M._reason(lp, M._null_mismatch(e, P)) if P else ("no_prediction", "")
                reasons[i][code] += 1
    raw = (ROOT/f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace"); meta = next(r for r in rows if r["slug"] == slug)
    vis = {}
    for nm, fn in (("sentence", process_paper), ("paragraph", process_paper_team)):
        pre = fn(slug, raw, meta, count, Options(), table); G = set().union(*(grams(s["clean"]) for s in pre.sidecar["sentences"])); vis[nm] = G
    never = [i for i in range(len(gold)) if found[i] == 0]
    hist = Counter(found[i] for i in range(len(gold)))
    out += [f"## {key}: {len(gold)} gold edges", f"- found by 0 runs: {len(never)}; by 1-2: {sum(hist[k] for k in (1,2))}; by 3-5: {sum(hist[k] for k in (3,4,5))}; by 6-8: {sum(hist[k] for k in (6,7,8))}", ""]
    cat = Counter(); 
    for i in never:
        e = gold[i]; gg = grams(e.sentences[0]) if e.sentences else set()
        v_s = len(gg & vis["sentence"])/max(1, len(gg)) >= .6; v_p = len(gg & vis["paragraph"])/max(1, len(gg)) >= .6
        top = reasons[i].most_common(1)[0][0]
        c = ("sentence not visible to the model" if not (v_s or v_p) else "visible, ") + ("" if not (v_s or v_p) else top)
        cat[c] += 1
        out.append(f"- [{e.edge_id}] {'NULL ' if e.null else ''}{M.readable_edge(e)}\n    visible: sentence-filter={v_s} paragraph={v_p}; dominant reason {top}; gold sentence: {(e.sentences[0] if e.sentences else '')[:150]}")
    out += ["", f"categories of the never-found edges: {dict(cat)}", ""]
    summary[key] = (len(gold), len(never), dict(cat))
open("dev/diag/7_never_found.md", "w").write("\n".join(out)); print(json.dumps(summary, indent=1))
