"""Score against the Murphy 2005 gold.

  python dev/eval_murphy.py --cached              re-run the CACHED model output for Murphy (baseline + Socratic prompt, sentence
                                                  filter) through the CURRENT preprocessing/expansion/guard code: an exact, noise-free
                                                  before/after check for post-processing changes (no LLM call; fails loudly on a cache miss)
  python dev/eval_murphy.py GRAPH.yaml [...]      score existing graphs (pipeline outputs) on Murphy (--others: also the other gold papers)
  EVAL_PREPROCESS=paragraph-chunks python dev/eval_murphy.py --cached --prompts system.txt    the paragraph-chunks model
  --json OUT                                      also write the numbers
"""
import argparse, csv, json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for k, v in (("BRINE_URL", "http://127.0.0.1:9/v1"), ("BRINE_MODEL", "Qwen3.8-27B"), ("BRINE_API_KEY", "unused")):
    os.environ.setdefault(k, v)
from dev.score.load import load_graph
from dev.score.metrics import score
SLUG, GOLD = "YKQQZV93", ROOT / "dev/gold/murphy2005.yaml"
PREPROCESS = os.environ.get("EVAL_PREPROCESS", "sentence")
OTHER = [("4CB9X9XE", ROOT / "dev/gold/4CB9X9XE.camo.yaml", None), ("3KPITIV3", ROOT / "dev/gold/3KPITIV3.yaml", None),
         ("6HKWT4QG", ROOT / "dev/gold/6HKWT4QG.yaml", None), ("ITXNQ843", ROOT / "dev/gold/ITXNQ843.yaml", None),
         ("2F76GVEE", ROOT / "dev/gold/2F76GVEE.yaml", None), ("4C479SU8", ROOT / "dev/gold/4C479SU8.yaml", None),
         ("V3H4MP29", ROOT / "dev/gold/V3H4MP29.yaml", None)]   # ITXNQ843, 3KPITIV3, 6HKWT4QG and these three are Claude drafts (silver)


def graph_from_cache(prompt: str, slugs=(SLUG,)) -> Path:
    from pipeline.extract import Client, config_from_env, extract_paper, load_prompt
    from pipeline.expand import expand_claims
    from pipeline.guard import guard_paper, merge
    from pipeline.main import get_preprocessor
    from pipeline.preprocess.assemble import Options
    from pipeline.preprocess.legend import load_taxon_table
    from pipeline.preprocess.tokens import get_counter
    from pipeline.write import write_yaml
    rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8"))}
    count, _ = get_counter(allow_download=False)
    _, system = load_prompt(prompt)
    cfg = config_from_env(False, True, 3000); cfg.url = "http://127.0.0.1:9/v1"; cfg.retries = 0
    per = {}
    for slug in slugs:
        raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace")
        pre = get_preprocessor(PREPROCESS)(slug, raw, rows[slug], count, Options(), load_taxon_table())
        ex = extract_paper(Client(cfg), system, pre.txt, [s["n"] for s in pre.sidecar["sentences"]], 12000, slug, pre.sidecar.get("chunk_texts"))
        exp = expand_claims(slug, ex.claims, pre.sidecar)
        nodes, edges, _ = guard_paper(slug, exp.nodes, exp.edges)
        per[slug] = (nodes, edges)
    g = merge([rows[s] for s in slugs], per)
    out = Path(tempfile.mkdtemp()) / f"murphy_{prompt}.yaml"
    write_yaml(g, out)
    return out


def murphy_score(path, gold_path=GOLD, gold_id="murphy2005", slug=SLUG) -> dict:
    gold = load_graph(gold_path, gold_id)
    pred = load_graph(path)
    key = next(iter(gold.edges_by_doc))
    pe = {slug: pred.edges_by_doc.get(slug, [])}
    s = score(gold.edges_by_doc, {}, pe, {key: slug})["modes"]["raw"]
    d = s["docs"][key]; L = d["levels"]; m = s["micro"]
    pairs = m.get("pairs") or {}
    return {"n_pred": d["n_pred"], "std_f1": L["standard"]["f1"], "std_p": L["standard"]["precision"], "std_r": L["standard"]["recall"],
            "strict_f1": L["strict"]["f1"], "loose_f1": L["loose"]["f1"], "null_recall": d["null"]["recall"], "null_precision": d["null"]["precision"],
            "lang_acc": pairs.get("causal_language_accuracy"), "pred_acc": pairs.get("predicate_accuracy")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graphs", nargs="*")
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--others", action="store_true", help="with --cached: also the other three gold papers (out-of-sample check)")
    ap.add_argument("--prompts", default="system.txt,system_socratic.txt")
    a = ap.parse_args()
    rows = []
    if a.cached:
        for p in a.prompts.split(","):
            slugs = (SLUG,) + (tuple(o[0] for o in OTHER) if a.others else ())
            gp = graph_from_cache(p, slugs)
            rows.append((f"Murphy cached {p} [{PREPROCESS}]", murphy_score(gp)))
            if a.others:
                for slug, gpath, gid in OTHER:
                    rows.append((f"  {slug} cached {p}", murphy_score(gp, gpath, gid, slug)))
    for g in a.graphs:
        rows.append((f"Murphy {g}", murphy_score(g)))
        if a.others:
            for slug, gpath, gid in OTHER:
                rows.append((f"  {slug}", murphy_score(g, gpath, gid, slug)))
    keys = ["n_pred", "std_f1", "std_p", "std_r", "strict_f1", "loose_f1", "null_recall", "null_precision", "lang_acc", "pred_acc"]
    print("| run | " + " | ".join(keys) + " |"); print("|---|" + "---:|" * len(keys))
    for name, r in rows:
        print(f"| {name} | " + " | ".join("—" if r[k] is None else (str(r[k]) if k == "n_pred" else f"{r[k]:.3f}") for k in keys) + " |")
    if a.json:
        json.dump(dict(rows), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
