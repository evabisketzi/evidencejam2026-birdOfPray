"""Score graphs on all eight reference papers, grouped: Murphy (human), dev3 (Claude, development), reg4 (Claude, fixed
regression set, not tuned on).  Claude references are the cleaned copies in dev/annot_v2/.

  python dev/eval8.py NAME=g1.yaml,g2.yaml,g3.yaml [NAME2=...] [--per-paper] [--json OUT]

Each NAME is one arm; its graphs are repeat runs (or replays of distinct response sets).  Prints mean [min-max] over runs;
dev3 / reg4 values are the mean over their papers within a run (macro).  Papers missing from a graph count as no output.
"""
import argparse, json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dev"))
from eval_murphy import murphy_score, GOLD, SLUG                 # noqa: E402

A2 = ROOT / "dev" / "annot_v2"
GROUPS = {"murphy": [(SLUG, GOLD, "murphy2005")],
          "dev3": [(s, A2 / f"{s}.yaml", None) for s in ("4CB9X9XE", "3KPITIV3", "6HKWT4QG")],
          "reg4": [(s, A2 / f"{s}.yaml", None) for s in ("ITXNQ843", "2F76GVEE", "4C479SU8", "V3H4MP29")]}
KEYS = ["n_pred", "std_f1", "std_p", "std_r", "strict_f1", "loose_f1", "null_recall", "lang_acc"]


def score_graph(g):
    per = {}
    for grp, items in GROUPS.items():
        for slug, gold, gid in items:
            per[slug] = (grp, murphy_score(g, gold, gid, slug))
    return per


def agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "—"
    m = statistics.mean(vals)
    return f"{m:.3f} [{min(vals):.3f}–{max(vals):.3f}]" if len(vals) > 1 else f"{m:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--per-paper", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = {}
    for arm in a.arms:
        name, gs = arm.split("=", 1)
        res[name] = [score_graph(g) for g in gs.split(",") if g]
    print("| arm | group | " + " | ".join(KEYS) + " |")
    print("|---|---|" + "---:|" * len(KEYS))
    for name, runs in res.items():
        for grp in GROUPS:
            cells = []
            for k in KEYS:
                per_run = []
                for per in runs:
                    v = [r[k] for g2, r in per.values() if g2 == grp and r[k] is not None]
                    per_run.append(statistics.mean(v) if v else None)
                cells.append(agg(per_run) if k != "n_pred" else agg(per_run).split(" ")[0])
            print(f"| {name} | {grp} | " + " | ".join(cells) + " |")
        if a.per_paper:
            for slug in [s for items in GROUPS.values() for s, _, _ in items]:
                cells = [agg([per[slug][1][k] for per in runs]) for k in KEYS]
                print(f"| {name} | {slug} | " + " | ".join(cells) + " |")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
