"""Papers where our baseline full graph shares no claim (loose) with Lane 2's graph: why?"""
import sys, json, csv, re, statistics as st; sys.path.insert(0, "dev/diag")
from collections import Counter
from common import *
SP = Path("/tmp/claude-1000/-home-kbuzko-Code-EvidenceJam/f78c8145-a29b-493a-b62b-29bd744228be/scratchpad")
S = json.load(open(SP / "lane2_vs_baseline/score.json"))["score"]["modes"]["raw"]
L2 = json.load(open(SP / "lanes/l2/causal_graph.json"))
dm = {r["gold_doc"]: r["pred_doc"] for r in csv.DictReader(open(SP / "lane2_docmap_all.csv"))}
l2nodes = {n["id"]: n for n in L2["nodes"]}
l2e = {}
for e in L2["edges"]: l2e.setdefault(e["source_document"], []).append(e)
ours = json.load(open(RUN / "full_baseline/camo_graph.json")); onodes = {n["id"]: n for n in ours["nodes"]}
oe = {}
for e in ours["edges"]: oe.setdefault(e["source_document"], []).append(e)
rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8"))}
count, _ = get_counter(allow_download=False); table = load_taxon_table()
def grams(t, k=4):
    w = re.findall(r"[a-z0-9]+", (t or "").lower()); return {tuple(w[i:i+k]) for i in range(max(1, len(w)-k+1))}
zero = [d for d, x in S["docs"].items() if x["n_gold"] and x["levels"]["loose"]["tp"] == 0]
out = ["# Papers with no overlap with Lane 2 (baseline full run)\n", f"{len(zero)} papers\n",
       "| slug | lane2 claims | our claims | lane2 sentences visible to our model | our res sentences | sections given | title |", "|---|---:|---:|---:|---:|---|---|"]
agg = Counter(); vis_all = []; detail = []
for d in zero:
    slug = dm[d]; E2 = l2e.get(d, []); E1 = oe.get(slug, [])
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace")
    pre = process_paper(slug, raw, rows[slug], count, Options(), table)
    G = set().union(*(grams(s["clean"]) for s in pre.sidecar["sentences"])) if pre.sidecar["sentences"] else set()
    vis = 0
    for e in E2:
        gg = grams(e.get("original_sentence", "").replace("...", ""))
        if gg and len(gg & G) / len(gg) >= 0.5: vis += 1
    vis_all.append((vis, len(E2)))
    secs = Counter(s["section"] for s in pre.sidecar["sentences"])
    out.append(f"| {slug} | {len(E2)} | {len(E1)} | {vis}/{len(E2)} | {secs.get('res', 0)} | {dict(secs)} | {rows[slug]['title'][:70]} |")
    detail.append((slug, E2[:3], E1[:3], pre.sidecar.get("sections_detected"), pre.sidecar.get("fallbacks")))
tv = sum(v for v, _ in vis_all); tn = sum(n for _, n in vis_all)
out += ["", f"Lane 2 claims in these papers: {tn}; their sentence visible to our model: {tv} ({tv/tn:.0%})",
        f"papers whose stage 1 found NO results section: {sum(1 for l in out if l.startswith('| ') and '| 0 |' in l.split('|',6)[-2:][0] if False)}"]
out += ["", "## Examples (first 3 claims each side)"]
for slug, E2, E1, secd, fb in detail:
    out.append(f"\n### {slug}  sections detected: {secd}  fallbacks: {fb}")
    for e in E2:
        out.append(f"- LANE2: {l2nodes[e['subject']]['name']} --{e['predicate']}--> {l2nodes[e['object']]['name']}   «{e.get('original_sentence','')[:120]}»")
    for e in E1:
        out.append(f"- OURS:  {onodes[e['subject']]['name']} --{e['predicate']}--> {onodes[e['object']]['name']}   «{e.get('original_sentence','')[:120]}»")
open("dev/diag/9_lane2_zero_overlap.md", "w").write("\n".join(out)); print("\n".join(out[:70]))
