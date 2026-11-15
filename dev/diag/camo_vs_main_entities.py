"""Which gold edges does graph A find at the LOOSE level (right pair of entities) that graph B misses, and how do the two
word the entities?  Built to decide the --entity-wording port: camo_pipeline finds about twice the out-of-sample loose
matches of the submitted pipeline (RESULTS.md, camo reference row).

    python dev/diag/camo_vs_main_entities.py A.yaml B.yaml [--docs SLUG,...] [--a-name camo] [--b-name main]

A = e.g. dev/diag/out/camo_ref.yaml (dev/diag/merge_graphs.py), B = a pipeline run's camo_graph.yaml on the gold papers.
Per paper: the gold edge, then A's nearest edge (found) and B's nearest candidate (missed, with the scorer's reason), and a
tally of how B's subject / object entity text differs.  Uses the team scorer (dev/score), no LLM."""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
for _k, _v in (("BRINE_URL", "http://127.0.0.1:9/v1"), ("BRINE_MODEL", "unused"), ("BRINE_API_KEY", "unused")):
    os.environ.setdefault(_k, _v)

from dev.eval_murphy import GOLD, OTHER, SLUG  # noqa: E402
from dev.results_table import NEW3  # noqa: E402
from dev.score.load import load_graph  # noqa: E402
from dev.score.metrics import score  # noqa: E402

GOLDS = [(SLUG, GOLD, "murphy2005")] + list(OTHER) + [(s, p, None) for s, p in NEW3]


def misses(pred_path: str, slug: str, gold_path, gold_id):
    """-> ({gold edge text: (reason, nearest candidate)} for gold edges with no LOOSE match, number of gold edges)."""
    gold = load_graph(gold_path, gold_id)
    key = next(iter(gold.edges_by_doc))
    pred = load_graph(pred_path)
    s = score(gold.edges_by_doc, {}, {slug: pred.edges_by_doc.get(slug, [])}, {key: slug})["modes"]["raw"]
    fn = {x["gold"]: (x["reason"], x["best_candidate"]) for x in s["fn"]}
    no_loose = {g: v for g, v in fn.items() if v[0].startswith("no loose match")}
    return no_loose, fn, s["docs"][key]["n_gold"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--docs", help="comma-separated slugs (default: every gold paper both graphs contain)")
    ap.add_argument("--a-name", default="A")
    ap.add_argument("--b-name", default="B")
    ap.add_argument("--limit", type=int, default=12, help="edges shown per paper")
    a = ap.parse_args(argv)
    present = set(load_graph(a.a).edges_by_doc) & set(load_graph(a.b).edges_by_doc)
    want = {d.strip() for d in a.docs.split(",")} if a.docs else present
    total = Counter()
    for slug, gpath, gid in GOLDS:
        if slug not in want or not Path(gpath).exists():
            continue
        a_miss, a_fn, n = misses(a.a, slug, gpath, gid)
        b_miss, _, _ = misses(a.b, slug, gpath, gid)
        only_a = [g for g in b_miss if g not in a_miss]
        only_b = [g for g in a_miss if g not in b_miss]
        total.update({"gold": n, f"loose only {a.a_name}": len(only_a), f"loose only {a.b_name}": len(only_b)})
        print(f"\n## {slug}: {n} gold edges; loose-found by {a.a_name} only: {len(only_a)}, by {a.b_name} only: {len(only_b)}")
        for g in only_a[:a.limit]:
            a_near = a_fn.get(g, ("(standard match)", "(matched at the standard level)"))[1]
            print(f"- gold:          {g}\n  {a.a_name + ' (found):':<14} {a_near}\n  {a.b_name + ' (missed):':<14} {b_miss[g][1]}")
    print("\n## total: " + ", ".join(f"{k} {v}" for k, v in total.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
