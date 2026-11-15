"""Score graphs and build the variant table of reports/RESULTS.md from per-run score files.

    python dev/results_table.py score OUT.json NAME=GRAPH.yaml [NAME=GRAPH.yaml ...]   add runs to a score file
    python dev/results_table.py table SCORES.json [SCORES.json ...] [--labels labels.csv]   print the markdown table

A score file has the format of reports/results/batch0_scores.json: {run: {paper: metrics}}, metrics as returned by
dev/eval_murphy.py murphy_score (n_pred, std_f1, std_p, std_r, strict_f1, loose_f1, null_recall, ...).  Paper keys:
"Murphy" (YKQQZV93) and the corpus slugs.  Runs named <variant>_r<k> are repeats of one variant; the table shows the mean
over repeats and [lowest-highest run].

Columns: Murphy (human gold); out-of-sample = mean over the four gold4 papers (4CB9X9XE, 3KPITIV3, 6HKWT4QG, ITXNQ843), the
same definition as RESULTS.md; new3 = mean over the three papers added on the harness branch (2F76GVEE, 4C479SU8, V3H4MP29),
shown only for runs that contain them, so the gold5 numbers stay comparable with the earlier rows.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for _k, _v in (("BRINE_URL", "http://127.0.0.1:9/v1"), ("BRINE_MODEL", "unused"), ("BRINE_API_KEY", "unused")):
    os.environ.setdefault(_k, _v)          # eval_murphy imports the pipeline config; scoring never calls the endpoint

GOLD4 = ["4CB9X9XE", "3KPITIV3", "6HKWT4QG", "ITXNQ843"]
NEW3 = [("2F76GVEE", ROOT / "dev/gold/2F76GVEE.yaml"), ("4C479SU8", ROOT / "dev/gold/4C479SU8.yaml"),
        ("V3H4MP29", ROOT / "dev/gold/V3H4MP29.yaml")]

# run-name prefix -> label, for the runs already in reports/results/batch0_scores.json (RESULTS.md wording)
DEFAULT_LABELS = {
    "tp_new_pc": "**paragraph-chunks, `system.txt` (submitted)**",
    "ctrl_sf": "sentence filter, `system.txt`",
    "tp_ctrl_pc": "paragraph-chunks, previous paragraph code",
    "v1_sf": "sentence filter, prompt `system_v1.txt`",
    "v1_pc": "paragraph-chunks, prompt `system_v1.txt`",
}


# ----------------------------------------------------------------------------------------------- score
def score_graph(path: str) -> Dict[str, dict]:
    from dev.eval_murphy import OTHER, murphy_score
    from dev.score.load import load_graph
    present = set(load_graph(path).edges_by_doc)
    out: Dict[str, dict] = {"Murphy": murphy_score(path)}
    for slug, gpath, gid in OTHER:
        out[slug] = murphy_score(path, gpath, gid, slug)
    for slug, gpath in NEW3:
        if slug in present and gpath.exists():
            out[slug] = murphy_score(path, gpath, None, slug)
    return out


def cmd_score(a) -> int:
    p = Path(a.out)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for item in a.runs:
        name, _, graph = item.partition("=")
        if not name or not graph:
            print(f"expected NAME=GRAPH, got {item!r}", file=sys.stderr)
            return 2
        if name in data and not a.overwrite:
            print(f"{name} is already in {p} (use --overwrite)", file=sys.stderr)
            return 2
        data[name] = score_graph(graph)
        m = data[name]["Murphy"]
        print(f"{name}: Murphy std F1 {m['std_f1']:.3f} (P {m['std_p']:.3f} R {m['std_r']:.3f}), "
              f"out-of-sample std F1 {mean(data[name][s]['std_f1'] for s in GOLD4):.3f}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return 0


# ----------------------------------------------------------------------------------------------- table
def variant_of(run: str) -> str:
    return re.sub(r"_r\d+$", "", run)


def _cell(vals: List[Optional[float]]) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "—"
    if len(vals) == 1:
        return f"{vals[0]:.3f}"
    return f"{mean(vals):.3f} [{min(vals):.3f}–{max(vals):.3f}]"


def _tok(vals: List[Optional[float]]) -> str:
    vals = [v for v in vals if v]
    return f"{mean(vals):,.0f}" if vals else "—"


COLUMNS = [
    ("Murphy std F1", lambda r: r["Murphy"]["std_f1"]),
    ("Murphy std P", lambda r: r["Murphy"]["std_p"]),
    ("Murphy std R", lambda r: r["Murphy"]["std_r"]),
    ("Murphy strict F1", lambda r: r["Murphy"]["strict_f1"]),
    ("Murphy loose F1", lambda r: r["Murphy"]["loose_f1"]),
    ("Murphy null recall", lambda r: r["Murphy"]["null_recall"]),
    ("Out-of-sample std F1", lambda r: mean(r[s]["std_f1"] for s in GOLD4)),
    ("Out-of-sample std P", lambda r: mean(r[s]["std_p"] for s in GOLD4)),
    ("Out-of-sample std R", lambda r: mean(r[s]["std_r"] for s in GOLD4)),
    ("Out-of-sample loose F1", lambda r: mean(r[s]["loose_f1"] for s in GOLD4)),
    ("new3 std F1", lambda r: mean(r[s]["std_f1"] for s, _ in NEW3) if all(s in r for s, _ in NEW3) else None),
    ("new3 loose F1", lambda r: mean(r[s]["loose_f1"] for s, _ in NEW3) if all(s in r for s, _ in NEW3) else None),
]


def build_table(runs: Dict[str, dict], labels: Dict[str, str], tokens: Dict[str, str]) -> str:
    variants: Dict[str, List[dict]] = {}
    for name, r in runs.items():
        variants.setdefault(variant_of(name), []).append(r)
    head = ["variant", "runs"] + [c for c, _ in COLUMNS] + ["Tokens per paper (in + out)"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    order = [v for v in labels if v in variants] + sorted(v for v in variants if v not in labels)
    for v in order:
        rs = variants[v]
        cells = [labels.get(v, v), str(len(rs))] + [_cell([f(r) for r in rs]) for _, f in COLUMNS] + [tokens.get(v, "—")]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cmd_table(a) -> int:
    runs: Dict[str, dict] = {}
    for f in a.scores:
        runs.update(json.loads(Path(f).read_text(encoding="utf-8")))
    labels, tokens = dict(DEFAULT_LABELS), {}
    if a.labels:
        with open(a.labels, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                labels[row["variant"]] = row["label"]
                if row.get("tokens"):
                    tokens[row["variant"]] = row["tokens"]
    print(build_table(runs, labels, tokens))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="score graphs into a score file")
    s.add_argument("out")
    s.add_argument("runs", nargs="+", metavar="NAME=GRAPH")
    s.add_argument("--overwrite", action="store_true")
    t = sub.add_parser("table", help="print the variant table")
    t.add_argument("scores", nargs="+")
    t.add_argument("--labels", help="csv: variant,label[,tokens]")
    a = ap.parse_args(argv)
    return cmd_score(a) if a.cmd == "score" else cmd_table(a)


if __name__ == "__main__":
    sys.exit(main())
