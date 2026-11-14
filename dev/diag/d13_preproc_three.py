"""Offline: what does each stage 1 SHOW the model? ours (sentence filter, current code) vs team old (pipeline/preprocess/team_paper.py)
vs team new (team/main 9b5f13c preprocess_paper.py, via the same adapter).  Gold-sentence visibility (fuzzy 4-gram >= 0.6),
null-sentence visibility, tokens; corpus-wide tokens and failures."""
import sys, csv, re, importlib.util, statistics as st, json; sys.path.insert(0, "dev/diag")
from common import *
import pipeline.preprocess.team_adapter as TA
from dev.score.load import load_graph
SP = "/tmp/claude-1000/-home-kbuzko-Code-EvidenceJam/f78c8145-a29b-493a-b62b-29bd744228be/scratchpad/teamnew/team_paper_new.py"
spec = importlib.util.spec_from_file_location("team_paper_new", SP); NEW = importlib.util.module_from_spec(spec); sys.modules["team_paper_new"] = NEW; spec.loader.exec_module(NEW)
OLD = TA.T
count, _ = get_counter(allow_download=False); table = load_taxon_table()
rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8"))}
def run(name, slug):
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace")
    if name == "ours": return process_paper(slug, raw, rows[slug], count, Options(), table)
    TA.T = OLD if name == "team old" else NEW
    try: return TA.process_paper_team(slug, raw, rows[slug], count, Options(), table)
    finally: TA.T = OLD
def grams(t, k=4):
    w = re.findall(r"[a-z0-9]+", (t or "").lower()); return {tuple(w[i:i+k]) for i in range(max(1, len(w)-k+1))}
GOLD = [("Murphy2005 (organisers, human)", "dev/gold/murphy2005.yaml", "murphy2005", "YKQQZV93"),
        ("4CB9X9XE (human)", "dev/gold/4CB9X9XE.camo.yaml", None, "4CB9X9XE"),
        ("3KPITIV3 (Claude silver)", "dev/gold/3KPITIV3.yaml", None, "3KPITIV3"),
        ("6HKWT4QG (Claude silver)", "dev/gold/6HKWT4QG.yaml", None, "6HKWT4QG"),
        ("ITXNQ843 (Claude silver)", "dev/gold/ITXNQ843.yaml", None, "ITXNQ843")]
V = ["ours", "team old", "team new"]
out = ["## Gold-cited sentences visible to the model (all edges / null edges), and input tokens\n",
       "| gold paper | " + " | ".join(V) + " |", "|---|" + "---:|" * len(V)]
tot = {v: [0, 0, 0, 0] for v in V}
for label, gp, gid, slug in GOLD:
    g = load_graph(ROOT / gp, gid); E = next(iter(g.edges_by_doc.values()))
    cells = []
    for v in V:
        pre = run(v, slug); G = set().union(*(grams(s["clean"]) for s in pre.sidecar["sentences"]))
        vis = lambda e: bool(e.sentences) and len(grams(e.sentences[0]) & G) / max(1, len(grams(e.sentences[0]))) >= 0.6
        a = sum(vis(e) for e in E); n = [e for e in E if e.null]; b = sum(vis(e) for e in n)
        tot[v][0] += a; tot[v][1] += len(E); tot[v][2] += b; tot[v][3] += len(n)
        cells.append(f"{a}/{len(E)} · nulls {b}/{len(n)} · {count(pre.txt):,} tok")
    out.append(f"| {label} | " + " | ".join(cells) + " |")
out.append("| **all 5** | " + " | ".join(f"**{t[0]}/{t[1]} ({t[0]/t[1]:.0%})** · nulls {t[2]}/{t[3]}" for t in tot.values()) + " |")
# corpus-wide
cw = {v: [] for v in V}; fails = {v: 0 for v in V}
for slug in rows:
    for v in V:
        pre = run(v, slug); cw[v].append(count(pre.txt))
        if v != "ours" and "team_preprocess" in pre.sidecar.get("fallbacks", []): fails[v] += 1
out += ["", "## All 308 papers", "| | " + " | ".join(V) + " |", "|---|" + "---:|" * len(V),
        "| total input tokens | " + " | ".join(f"{sum(cw[v]):,}" for v in V) + " |",
        "| median per paper | " + " | ".join(f"{st.median(cw[v]):,.0f}" for v in V) + " |",
        "| papers where the team code failed (fell back to ours) | — | " + " | ".join(str(fails[v]) for v in V[1:]) + " |"]
open("dev/diag/13_preproc_three.md", "w").write("\n".join(out)); print("\n".join(out))
