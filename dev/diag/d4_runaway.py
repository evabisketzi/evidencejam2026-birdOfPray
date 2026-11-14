import sys, json, re, statistics as st; sys.path.insert(0, "dev/diag")
from collections import Counter
from common import *
from pipeline.expand import Expander
from pipeline.parse import parse_text
G = json.load(open(RUN / "full_baseline/camo_graph.json"))
final = Counter(e["source_document"] for e in G["edges"])
o = ["# Runaway papers, baseline (cached full_baseline extraction; no new LLM calls)\n"]
for slug in ("4C479SU8", "DX4T38CC", "IBH9XBA8"):
    pre, ex = cached_extraction(slug)
    side = pre.sidecar
    sent = {s["n"]: s for s in side["sentences"]}
    per = []                                   # (claim, edges produced by that line)
    for c in ex.claims:
        e = Expander(slug, side)
        out = e.expand([c])
        per.append((c, out.edges))
    fan = [len(es) for _, es in per]
    eff = [len(c.effects) for c, _ in per]
    total = sum(fan)
    med_claims = [c for c, _ in per if c.keys.get("med")]
    med_edges = sum(1 for _, es in per for x in es if x.get("mediation")) 
    path_edges = sum(len(es) - len(c.effects) for c, es in per if c.keys.get("med"))
    cite = Counter()
    for c, es in per:
        for n in c.sentences:
            cite[n] += len(es)
    raw_lines = sum(len(r.splitlines()) for r in ex.raw)
    o += [f"## {slug}", f"- final edges in full_baseline graph: {final[slug]}; edges expanded from parsed lines: {total}",
          f"- raw model lines: {raw_lines}; parsed claims: {len(ex.claims)}; bad lines {ex.n_bad}; completion tokens {ex.completion_tokens}; sentences given: {len(side['sentences'])}",
          f"- fan-out per line (edges per line): max {max(fan)}, median {st.median(fan)}, mean {st.mean(fan):.1f}; effects per line: max {max(eff)}, median {st.median(eff)}",
          f"- lines using a mediator (med=): {len(med_claims)}; edges carrying a mediation field: {med_edges}; extra path edges generated for them: {path_edges}",
          f"- edges per line, top 5 lines: " + "; ".join(f"{len(es)} edges <- {c.raw[:150]}" for c, es in sorted(per, key=lambda t: -len(t[1]))[:5]),
          "", "### 5 most-cited sentences (edges citing them)"]
    for n, k in cite.most_common(5):
        s = sent.get(n, {})
        o.append(f"- [{n}] ({s.get('section')}) {k} edges: {s.get('raw','')[:400]}")
    raw_md = (ROOT / "corpus" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    from pipeline.preprocess.clean import _is_table_row
    trows = [l for l in raw_md.splitlines() if _is_table_row(l)]
    pipe_sent = [s for s in side["sentences"] if "|" in s["raw"]]
    numeric = []
    for s in side["sentences"]:
        toks = s["raw"].split()
        if len(toks) >= 6 and sum(1 for t in toks if re.fullmatch(r"[-−+±(]?\d[\d.,]*[%)a-z]{0,2}", t)) / len(toks) >= 0.4: numeric.append(s)
    caps = [s for s in side["sentences"] if s["section"] == "cap"]
    o += ["", "### Did table text reach the numbered sentences?",
          f"- raw markdown table-like lines (pipe/numeric rows): {len(trows)}; sample: {trows[:2]}",
          f"- numbered sentences containing '|': {len(pipe_sent)}; mostly-numeric sentences: {len(numeric)}; caption sentences (tag cap): {len(caps)}",
          f"- sentence sections: {dict(Counter(s['section'] for s in side['sentences']))}; dropped by preprocessing: {len(side['dropped'])}"]
    for s in (pipe_sent + numeric)[:3]:
        o.append(f"  example: [{s['n']}] ({s['section']}) {s['raw'][:300]}")
    o.append("")
open("dev/diag/4_runaway_papers.md", "w").write("\n".join(o))
print("\n".join(o))
