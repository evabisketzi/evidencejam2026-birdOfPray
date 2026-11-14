"""Where do we lose? Failure budget on the 5 gold papers (cached output, current code), both stage-1 models, plus duplication corpus-wide."""
import sys, os, json, collections, re, yaml; sys.path.insert(0, "dev")
from eval_murphy import *
from dev.score.match import match_document
from dev.score import metrics as M
from dev.score.normalise import norm_tokens
G = {"YKQQZV93": ("dev/gold/murphy2005.yaml", "murphy2005"), "4CB9X9XE": ("dev/gold/4CB9X9XE.camo.yaml", None),
     "3KPITIV3": ("dev/gold/3KPITIV3.yaml", None), "6HKWT4QG": ("dev/gold/6HKWT4QG.yaml", None),
     "ITXNQ843": ("dev/gold/ITXNQ843.yaml", None)}
def key(e, nodes):
    s, o = nodes[e["subject"]], nodes[e["object"]]
    return (" ".join(sorted(set(norm_tokens(s["name"])))), e["predicate"], " ".join(sorted(set(norm_tokens(o["name"])))), bool(e.get("negated")))
def dup_rate(edges, nodes):
    c = collections.Counter(key(e, nodes) for e in edges); extra = sum(v - 1 for v in c.values())
    return extra, len(edges)
pp = os.environ.get("EVAL_PREPROCESS", "sentence")
p = graph_from_cache("system.txt", tuple(G))
pred_raw = yaml.safe_load(open(p)); pn = {n["id"]: n for n in pred_raw["nodes"]}
tot = collections.Counter(); fn_c = collections.Counter(); fp_c = collections.Counter(); ng = npred = 0
lang_pairs = collections.Counter(); pred_pairs = collections.Counter()
dups = [0, 0]; gdups = [0, 0]
for slug, (gp, gid) in G.items():
    gold = load_graph(ROOT / gp, gid); k = next(iter(gold.edges_by_doc)); Ge = gold.edges_by_doc[k]
    Pe = load_graph(p).edges_by_doc.get(slug, [])
    ng += len(Ge); npred += len(Pe)
    m = match_document(Ge, Pe, 0.5); std = {x.i for x in m.level("standard")}; stdj = {x.j for x in m.level("standard")}
    by_g = {x.i: x for x in m.pairs}; by_p = {x.j: x for x in m.pairs}
    for i, g in enumerate(Ge):
        if i not in std:
            lp = by_g.get(i); fn_c[M._reason(lp, M._null_mismatch(g, Pe))[0] if lp or Pe else "no_prediction"] += 1
    for x in m.level("loose"):
        lang_pairs[(Ge[x.i].causal_language, Pe[x.j].causal_language)] += 1
        pred_pairs[(Ge[x.i].predicate, Pe[x.j].predicate)] += 1
    # FP: unmatched predicted edges; is it a duplicate of a matched one (same gold edge already taken)?
    loose_g = collections.defaultdict(list)
    for i, g in enumerate(Ge):
        for j, q in enumerate(Pe):
            if m.loose[i, j] if hasattr(m, "loose") else False: loose_g[j].append(i)
    for j, q in enumerate(Pe):
        if j in stdj: continue
        lp = by_p.get(j)
        if lp is not None: fp_c[M._reason(lp, False)[0]] += 1
        else: fp_c["no_loose_match"] += 1
    E = [e for e in pred_raw["edges"] if e["source_document"] == slug]
    a, b = dup_rate(E, pn); dups[0] += a; dups[1] += b
    gd = yaml.safe_load(open(ROOT / gp)); gg = [x["graph"] for x in gd["graphs"]] if "graphs" in gd else [gd]
    gnodes = {n["id"]: n for g2 in gg for n in g2["nodes"]}; gedges = [e for g2 in gg for e in g2["edges"]]
    a, b = dup_rate(gedges, gnodes); gdups[0] += a; gdups[1] += b
tp = sum(1 for _ in [])  # placeholder
print(f"=== model: {pp}; {len(G)} gold papers: gold edges {ng}, ours {npred}")
print("missed gold edges (FN) by reason:", dict(fn_c.most_common()))
print("our extra edges (FP) by reason:   ", dict(fp_c.most_common()))
print(f"duplicates (same subject/predicate/object/null after normalising names): ours {dups[0]} of {dups[1]} edges ({dups[0]/dups[1]:.0%}); gold {gdups[0]} of {gdups[1]} ({gdups[0]/gdups[1]:.0%})")
L = sum(lang_pairs.values()); over = sum(v for (g, q), v in lang_pairs.items() if q == "direct_causal" and g != "direct_causal")
under = sum(v for (g, q), v in lang_pairs.items() if g == "direct_causal" and q != "direct_causal")
print(f"causal language on {L} matched pairs: agree {sum(v for (g,q),v in lang_pairs.items() if g==q)}; we say direct where gold does not {over}; gold direct, we weaker {under}")
P = sum(pred_pairs.values()); pc = sum(v for (g, q), v in pred_pairs.items() if q == "causes" and g != "causes")
print(f"predicate on matched pairs: agree {sum(v for (g,q),v in pred_pairs.items() if g==q)} of {P}; we say 'causes' where gold says something else {pc}: {collections.Counter(g for (g,q),v in pred_pairs.items() for _ in range(v) if q=='causes' and g!='causes').most_common(4)}")
