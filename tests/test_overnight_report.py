"""The winner rule, the Phase A comparison and the morning report (dev/overnight_report.py), on synthetic score files."""
import csv
import json
import time
from pathlib import Path

import pytest

from dev import overnight_report as R


def variant(f1, null_recall, fn=(), fp=(), tokens=(5000, 120, 10.0)):
    lv = {k: {"precision": f1, "recall": f1, "f1": f1, "tp": 1, "fp": 0, "fn": 0} for k in ("strict", "standard", "loose")}
    null = {"precision": 0.5, "recall": null_recall}
    pairs = {"causal_language_accuracy": 0.9}
    return {"raw": {"micro": {"levels": lv, "null": null, "pairs": pairs, "findings": {"recall": 0.5}},
                    "docs": {"g1": {"pred_doc": "P1", "levels": lv, "null": null, "pairs": pairs, "findings": None}},
                    "fn": list(fn), "fp": list(fp)}, "tokens": {"P1": {"p": tokens[0], "c": tokens[1], "s": tokens[2]}}}


@pytest.mark.parametrize("fb,fs,nb,ns,winner", [
    (0.40, 0.45, 0.0, 0.0, "socratic"),          # +0.05 exactly
    (0.40, 0.449, 0.0, 0.0, "baseline"),         # just under +0.05
    (0.40, 0.42, 0.10, 0.25, "socratic"),        # within 0.02 and null recall +0.15
    (0.40, 0.42, 0.10, 0.24, "baseline"),        # null recall only +0.14
    (0.40, 0.43, 0.10, 0.50, "baseline"),        # F1 +0.03: neither "+0.05" nor "within 0.02"
    (0.40, 0.38, 0.10, 0.30, "socratic"),        # -0.02 is still within 0.02
    (0.40, 0.37, 0.10, 0.30, "baseline"),        # -0.03 is not
    (0.40, 0.30, 0.0, 0.9, "baseline"),
])
def test_winner_rule(fb, fs, nb, ns, winner):
    got, why = R.decide({"baseline": variant(fb, nb), "socratic": variant(fs, ns)})
    assert got == winner and "micro standard F1" in why


def test_missing_variants_default_to_baseline_and_say_so():
    assert R.decide({"baseline": variant(0.4, 0), "socratic": None})[0] == "baseline"
    w, why = R.decide({"baseline": None, "socratic": variant(0.9, 1.0)})
    assert w == "baseline" and "cannot be evaluated" in why
    assert R.decide({"baseline": None, "socratic": None})[0] == "baseline"


def fn_entry(edge, code="attribute_differs", finding="f1"):
    return {"doc": "g1", "finding": finding, "gold_edge": edge, "gold": f"[Increased] X {edge} --causes--> [Decreased] Y",
            "reason": "right entities, object attribute differs (similarity 0.00)", "reason_code": code}


def write_dev(run: Path, name: str, v: dict, fn, fp):
    d = run / f"dev_{name}"
    (d / "score").mkdir(parents=True)
    score = {"score": {"modes": {"raw": {**v["raw"], "fn": fn, "fp": fp}}}}
    (d / "score" / "score.json").write_text(json.dumps(score))
    with open(d / "tokens.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc", "prompt_tokens", "completion_tokens", "seconds", "chunks", "thinking"])
        t = v["tokens"]["P1"]
        w.writerow(["P1", t["p"], t["c"], t["s"], 1, "off"])


def test_compare_writes_table_reason_counts_symmetric_differences_and_winner(tmp_path):
    base_fn = [fn_entry("e1"), fn_entry("e2", "no_loose_match"), fn_entry("e3", "null_mismatch")]
    soc_fn = [fn_entry("e2", "no_loose_match"), fn_entry("e4", "opposite_direction")]
    write_dev(tmp_path, "baseline", variant(0.40, 0.2, tokens=(5000, 100, 30.0)), base_fn, [])
    write_dev(tmp_path, "socratic", variant(0.46, 0.2, tokens=(5200, 140, 45.0)), soc_fn, [{"reason_code": "attribute_differs"}])
    winner, why = R.compare(tmp_path)
    md = (tmp_path / "dev_comparison.md").read_text()
    assert winner == "socratic" and (tmp_path / "winner.txt").read_text().strip() == "system_socratic.txt"
    assert "| baseline | g1 |" in md and "| **socratic** | **micro** |" in md and "5200" in md and "140" in md and "45" in md
    assert "| baseline | false negatives | 1 | 1 | 0 | 1 | 0 |" in md                      # reason counts per variant
    assert "| socratic | false negatives | 1 | 0 | 1 | 0 | 0 |" in md
    assert "Found by baseline, missed by Socratic: 1 gold edge" in md and "e4" in md      # socratic missed e4
    assert "Found by Socratic, missed by baseline: 2 gold edge" in md and "e1" in md and "e3" in md
    assert "**socratic** (system_socratic.txt)" in md


def test_compare_lists_at_most_15_differences_each_way(tmp_path):
    write_dev(tmp_path, "baseline", variant(0.4, 0), [fn_entry(f"b{i}") for i in range(20)], [])
    write_dev(tmp_path, "socratic", variant(0.4, 0), [], [])
    R.compare(tmp_path)
    md = (tmp_path / "dev_comparison.md").read_text()
    assert "Found by Socratic, missed by baseline: 20 gold edge(s) (first 15 shown)" in md and md.count("`[Increased] X b") == 15


def test_compare_survives_a_failed_variant(tmp_path):
    write_dev(tmp_path, "baseline", variant(0.4, 0), [], [])
    winner, why = R.compare(tmp_path)
    assert winner == "baseline" and "no score" in (tmp_path / "dev_comparison.md").read_text()


def make_full(run: Path, name: str, per_paper: dict, failed=(), valid=True, retries=0):
    d = run / f"full_{name}"
    d.mkdir(parents=True)
    papers = [{"doc": s, "error": None, "prompt_tokens": 5000 + i, "completion_tokens": 100 + 10 * i, "seconds": 5, "chunks": 1}
              for i, s in enumerate(per_paper)]
    papers += [{"doc": s, "error": "LLMError: request failed after 4 attempts (HTTP 503)", "prompt_tokens": 0, "completion_tokens": 0,
                "seconds": 0, "chunks": 0} for s in failed]
    (d / "run_log.json").write_text(json.dumps({"papers": papers}))
    edges = [{"id": f"{s}-e{k}", "source_document": s, "negated": (k == 0)} for s, n in per_paper.items() for k in range(n)]
    (d / "camo_graph.json").write_text(json.dumps({"edges": edges, "nodes": [{"id": "n"}] * 3}))
    (d / "validation.json").write_text(json.dumps({"ok": valid, "yaml_ok": valid, "json_ok": True, "validators": "JSON Schema + linkml-validate",
                                                   "errors": [] if valid else ["camo_graph.yaml: boom"]}))
    with open(d / "retries.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(R.__dict__.get("RETRY_HEADER", ["timestamp", "doc", "attempt", "error", "sleep_s", "gave_up"]))
        for i in range(retries):
            w.writerow(["t", "A", i + 1, "HTTP 503", 2, 0])


def test_morning_report_has_everything_asked_for(tmp_path):
    t = time.time()
    (tmp_path / "phases.tsv").write_text(
        f"tests\t{t}\t{t + 40}\tok\t\ndev_baseline\t{t + 40}\t{t + 100}\tok\t\nfull_baseline\t{t + 100}\t{t + 100 + 3700}\tok\t\n"
        f"full_socratic\t{t + 3800}\t{t + 3800}\tskipped\tphase B took 14000 s\nfull_socratic\t{t}\t{t}\tfailed\tboom\n")
    make_full(tmp_path, "baseline", {"A1": 10, "A2": 0, "A3": 30, "A4": 20}, failed=["A5"], retries=3)
    R.report(tmp_path)
    md = (tmp_path / "REPORT.md").read_text()
    assert "4 ok" in md and "1 failed" in md and "request failed after 4 attempts" in md
    assert "retries: 3 logged" in md and "1:01:40" in md                                    # wall clock of the phase
    assert "60 edges, 3 nodes, 3 null results" in md
    assert "median 10.0" in md and "min 0" in md and "max 30" in md                         # over the 5 attempted papers
    assert "papers with 0 edges (2): A2, A5" in md
    assert "YAML OK, JSON OK" in md
    assert "not completed" in md                                                            # socratic never ran
    assert "## 4. Timing" in md and "| tests |" in md and "Problems:" in md and "Skipped:" in md


def test_report_side_by_side_with_the_ten_biggest_differences(tmp_path):
    t = time.time()
    (tmp_path / "phases.tsv").write_text(f"full_baseline\t{t}\t{t + 10}\tok\t\nfull_socratic\t{t + 10}\t{t + 30}\tok\t\n")
    a = {f"P{i:02d}": 10 for i in range(12)}
    b = {f"P{i:02d}": 10 + (i if i % 2 else -i % 10) for i in range(12)}
    make_full(tmp_path, "baseline", a)
    make_full(tmp_path, "socratic", b)
    R.report(tmp_path)
    md = (tmp_path / "REPORT.md").read_text()
    assert "## 3. Baseline vs Socratic, side by side" in md and "| edges | 120 |" in md
    table = md.split("Ten papers where the variants differ most in edge count:")[1].split("## 4.")[0]
    rows = [ln for ln in table.splitlines() if ln.startswith("| P")]
    assert len(rows) == 10 and rows[0].startswith("| P11 |")                                  # the largest difference first
