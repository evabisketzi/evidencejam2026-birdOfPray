"""python dev/preproc_compare_report.py RUN_DIR [RUN_DIR ...]  -> markdown: mean (min-max) over repeats per preprocessing.

Run dirs hold VARIANT_REP folders (e.g. sentence_1, paragraph-chunks_2).  With several RUN_DIRs (e.g. one on the original two gold
papers, one on the two newer ones), the folders with the same VARIANT_REP are pooled: micro scores are recomputed from the per-paper
counts of all papers."""
import csv, json, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = {"ours": "sentence filter (ours)", "sentence": "sentence filter (ours)", "team": "paragraph selection (teammate)",
         "paragraph": "paragraph selection (teammate)", "paragraph-chunks": "paragraph selection, one call per chunk"}
CANON = {"ours": "sentence", "team": "paragraph"}
SHORT = {r["gold_doc"]: r["pred_doc"] for r in csv.DictReader(open(ROOT / "dev/gold/doc_map.csv"))}
SHORT["murphy2005"] = "Murphy2005"



def collect(dirs):
    runs = {}                       # (variant, rep) -> {"docs": {doc: dict}, "papers": [run_log rows]}
    for run in dirs:
        for d in sorted(Path(run).glob("*_[0-9]*")):
            if not (d.is_dir() and (d / ".done").exists()):
                continue
            v, rep = d.name.rsplit("_", 1)
            r = runs.setdefault((CANON.get(v, v), rep), {"docs": {}, "papers": []})
            s = json.load(open(d / "score/score.json"))["score"]["modes"]["raw"]
            r["docs"].update(s["docs"])
            r["papers"] += json.load(open(d / "run_log.json"))["papers"]
    return runs


def metrics(r):
    out = {}
    G = sum(x["n_gold"] for x in r["docs"].values()); P = sum(x["n_pred"] for x in r["docs"].values())
    for lv in ("standard", "strict", "loose"):
        t = sum(x["levels"][lv]["tp"] for x in r["docs"].values())
        p = t / P if P else 0; rc = t / G if G else 0
        out[lv] = 2 * p * rc / (p + rc) if p + rc else 0
        if lv == "standard":
            out["P"], out["R"] = p, rc
    gn = sum(x["null"]["gold_null"] for x in r["docs"].values()); mn = sum(x["null"]["matched"] for x in r["docs"].values())
    out["null_r"] = mn / gn if gn else None
    out["n_pred"] = P
    out["prompt"] = sum(p["prompt_tokens"] for p in r["papers"]); out["compl"] = sum(p["completion_tokens"] for p in r["papers"])
    for doc, x in r["docs"].items():
        name = SHORT.get(doc, doc)
        out[f"std {name}"] = x["levels"]["standard"]["f1"]; out[f"strict {name}"] = x["levels"]["strict"]["f1"]
        out[f"null recall {name}"] = x["null"]["recall"]
    return out


def main(dirs):
    runs = collect(dirs)
    data = {}
    for (v, rep), r in runs.items():
        data.setdefault(v, []).append(metrics(r))
    docs = sorted({SHORT.get(d, d) for r in runs.values() for d in r["docs"]})
    names = sorted(data, key=lambda n: ["sentence", "paragraph", "paragraph-chunks"].index(n) if n in ("sentence", "paragraph", "paragraph-chunks") else 9)

    def fmt(v, big):
        return "—" if v is None else (f"{v:,.0f}" if big else f"{v:.3f}")

    def cell(rows, k, big=False):
        xs = [r[k] for r in rows if r.get(k) is not None]
        if not xs:
            return "—"
        return f"{fmt(st.mean(xs), big)} ({fmt(min(xs), big)}–{fmt(max(xs), big)})" if len(xs) > 1 else fmt(xs[0], big)

    print(f"# Preprocessing comparison ({', '.join(Path(d).name for d in dirs)}); papers: {', '.join(docs)}; mean (min–max) over repeats\n")
    print("**sentence filter (ours):** split into sentences, drop cited-background sentences, compress statistics. **paragraph selection "
          "(teammate):** clean paragraphs, drop introduction/methods, keep paragraphs by cue score, then split into sentences; whole paper in "
          "one call. **paragraph selection, one call per chunk:** the same sentences, grouped by the teammate's pack() into chunks of <= 2,500 "
          "tokens of paragraph text, one LLM call per chunk (header repeated). Same prompt, SPECIES and CONTEXT in all; cache off.\n")
    print("| metric | " + " | ".join(f"{LABEL[n]} (n={len(data[n])})" for n in names) + " |")
    print("|---|" + "---:|" * len(names))
    rows = [("micro standard F1", "standard", 0), ("micro strict F1", "strict", 0), ("micro loose F1", "loose", 0),
            ("standard precision", "P", 0), ("standard recall", "R", 0), ("null recall", "null_r", 0), ("predicted edges", "n_pred", 1),
            ("prompt tokens", "prompt", 1), ("completion tokens", "compl", 1)]
    for d in docs:
        rows += [(f"standard F1 {d}", f"std {d}", 0), (f"strict F1 {d}", f"strict {d}", 0), (f"null recall {d}", f"null recall {d}", 0)]
    for label, k, big in rows:
        print(f"| {label} | " + " | ".join(cell(data[n], k, big) for n in names) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
