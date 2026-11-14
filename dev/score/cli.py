"""python -m dev.score.cli --gold G.yaml [--gold-doc-id ID] [--gold H.yaml ...] --pred P.yaml [--doc-map map.csv]
                          [--collapse] [--threshold 0.6] [--tokens tokens.csv] [--validate] --out dir/
   python -m dev.score.cli --self-test [--gold ...]        (default: the gold files in dev/gold/)"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .load import load_doc_map, load_graph, merge_loaded
from .metrics import LEVELS, linkml_validate, load_tokens, score, validity_checks
from .report import write_reports

ROOT = Path(__file__).resolve().parent.parent.parent


class _GoldAction(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        items = list(getattr(ns, "gold") or [])
        items.append({"path": values, "doc_id": None})
        ns.gold = items


class _GoldDocAction(argparse.Action):
    """--gold-doc-id applies to the --gold given just before it."""
    def __call__(self, parser, ns, values, option_string=None):
        if not getattr(ns, "gold", None):
            parser.error("--gold-doc-id must come after the --gold it names")
        ns.gold[-1]["doc_id"] = values


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dev.score.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", action=_GoldAction, default=None, help="gold file (repeatable): CausalGraph or interstitial wrapper")
    ap.add_argument("--gold-doc-id", action=_GoldDocAction, help="document id for the preceding --gold wrapper file")
    ap.add_argument("--pred", help="predicted CausalGraph (or wrapper)")
    ap.add_argument("--pred-doc-id", help="document id when --pred is a wrapper file")
    ap.add_argument("--doc-map", help="csv: gold_doc,pred_doc")
    ap.add_argument("--collapse", action="store_true", help="make collapse mode the primary one for error lists (both are always reported)")
    ap.add_argument("--threshold", type=float, default=0.5, help="object-attribute similarity needed for the standard level")
    ap.add_argument("--sensitivity", default="0.3,0.4,0.5,0.6,0.7,0.8", help="thresholds for the sensitivity table")
    ap.add_argument("--tokens", help="csv: doc,prompt_tokens,completion_tokens")
    ap.add_argument("--validate", action="store_true", help="also run linkml-validate on --pred")
    ap.add_argument("--max-errors", type=int, default=25)
    ap.add_argument("--out", default="dev/score_out")
    ap.add_argument("--self-test", action="store_true", help="score each gold file against itself; every F1 must be 1.0")
    return ap


def _load_gold(items):
    loaded = [load_graph(i["path"], i["doc_id"]) for i in items]
    return merge_loaded(loaded)


def self_test(items) -> int:
    items = items or [{"path": str(p), "doc_id": p.name.split(".")[0].lower() if p.name.lower().startswith("murphy") else None}
                      for p in sorted((ROOT / "dev" / "gold").glob("*.yaml"))]
    bad = 0
    for it in items:
        e, fnd = _load_gold([it])
        res = score(e, fnd, e, None)
        for mode in ("raw", "collapse"):
            lv = res["modes"][mode]["micro"]["levels"]
            ok = all(abs(lv[l]["f1"] - 1.0) < 1e-12 for l in LEVELS) and res["modes"][mode]["micro"]["n_gold"] > 0
            bad += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {Path(it['path']).name:<24} {mode:<8} "
                  + "  ".join(f"{l} F1={lv[l]['f1']:.3f}" for l in LEVELS) + f"  ({res['modes'][mode]['micro']['n_gold']} edges)")
    print("self-test " + ("FAILED" if bad else "passed"))
    return 1 if bad else 0


def main(argv: Optional[List[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    if a.self_test:
        return self_test(a.gold)
    if not a.gold or not a.pred:
        build_parser().error("--gold and --pred are required (or use --self-test)")
    gold_edges, gold_findings = _load_gold(a.gold)
    pred = load_graph(a.pred, a.pred_doc_id)
    docmap = load_doc_map(a.doc_map)
    tokens = load_tokens(a.tokens) if a.tokens else None
    sens = [float(x) for x in a.sensitivity.split(",") if x.strip()]
    res = score(gold_edges, gold_findings, pred.edges_by_doc, docmap, a.threshold, tokens, sens)
    validity = validity_checks(pred.raw_graphs)
    validate = linkml_validate(a.pred) if a.validate else None
    primary = "collapse" if a.collapse else "raw"
    meta = {"gold": [i["path"] for i in a.gold], "pred": a.pred, "doc_map": a.doc_map, "threshold": a.threshold}
    write_reports(a.out, res, validity, validate, primary, a.max_errors, meta)
    raw = res["modes"]["raw"]["micro"]
    print(f"standard F1 raw={raw['levels']['standard']['f1']:.3f} collapse={res['modes']['collapse']['micro']['levels']['standard']['f1']:.3f}"
          f"  (report: {a.out}/score.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
