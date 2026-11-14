"""Offline comparison of our stage 1 and the teammate's: input size over the whole corpus, and the recall ceiling on the gold papers."""
import sys, csv, json, re, statistics as st; sys.path.insert(0, "dev/diag")
from common import *
from pipeline.preprocess.team_adapter import process_paper_team
from dev.score.load import load_graph
count, _ = get_counter(allow_download=False)
table = load_taxon_table()
rows = list(csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8")))
res = {}
for r in rows:
    s = r["slug"]; raw = (ROOT / f"corpus/{s}.md").read_text(encoding="utf-8", errors="replace")
    a = process_paper(s, raw, r, count, Options(), table)
    b = process_paper_team(s, raw, r, count, Options(), table)
    res[s] = {"ours_tok": count(a.txt), "team_tok": count(b.txt), "ours_n": len(a.sidecar["sentences"]), "team_n": len(b.sidecar["sentences"]),
              "team_fb": "team_preprocess" in b.sidecar["fallbacks"]}
json.dump(res, open("dev/diag/5_corpus_sizes.json", "w"))
def tot(k): return sum(v[k] for v in res.values())
o = ["# Stage-1 comparison: ours vs teammate's (offline, no LLM)\n",
     f"papers: {len(res)}; teammate preprocessing fell back to ours on {sum(v['team_fb'] for v in res.values())}",
     f"input tokens (our tokenizer, whole TITLE/SPECIES/CONTEXT/TEXT): ours {tot('ours_tok'):,} (median {st.median(v['ours_tok'] for v in res.values())}), team {tot('team_tok'):,} (median {st.median(v['team_tok'] for v in res.values())}); ratio team/ours {tot('team_tok')/tot('ours_tok'):.2f}",
     f"numbered sentences: ours {tot('ours_n'):,}, team {tot('team_n'):,}\n"]
def norm(t): return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
for gold_path, gid, slug in (("dev/gold/murphy2005.yaml", "murphy2005", "YKQQZV93"), ("dev/gold/4CB9X9XE.camo.yaml", None, "4CB9X9XE")):
    g = load_graph(ROOT / gold_path, gid); key = next(iter(g.edges_by_doc)); gold = g.edges_by_doc[key]
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace"); meta = next(r for r in rows if r["slug"] == slug)
    for name, fn in (("ours", process_paper), ("team", process_paper_team)):
        pre = fn(slug, raw, meta, count, Options(), table)
        sents = pre.sidecar["sentences"]
        blob = norm(" ".join(s["clean"] for s in sents))
        spans = [(s["start_char"], s["end_char"]) for s in sents]
        cov = 0; cov_txt = 0; n = 0
        for e in gold:
            n += 1
            sp = [(a, b) for a, b, _ in e.spans if a is not None]
            hit_off = any(a < d and c < b for a, b in sp for c, d in spans) if sp else False
            txt = norm(e.sentences[0]) if e.sentences else ""
            hit_txt = bool(txt) and (txt[:60] in blob)
            cov += hit_off; cov_txt += hit_txt
        o.append(f"- {key} / {name}: sentences {len(sents)}, input tokens {count(pre.txt)}; gold edges whose cited sentence is available to the model: by offsets {cov}/{n}, by text (first 60 chars) {cov_txt}/{n}")
open("dev/diag/5_preprocess_compare_offline.md", "w").write("\n".join(o))
print("\n".join(o))
