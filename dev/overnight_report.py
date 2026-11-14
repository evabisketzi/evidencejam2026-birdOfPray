#!/usr/bin/env python3
"""Reports for dev/overnight.sh.

    python dev/overnight_report.py compare RUN_DIR   # phase A: dev_comparison.md + winner.txt (prints the winning prompt file)
    python dev/overnight_report.py report  RUN_DIR   # phase D: REPORT.md

RUN_DIR = dev/overnight/<timestamp>/ with dev_baseline/, dev_socratic/, full_baseline/, full_socratic/, phases.tsv.
Everything is read defensively: a missing or broken piece is reported, never raised, so the morning report always gets written."""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VARIANTS = [("baseline", "system.txt"), ("socratic", "system_socratic.txt")]
CODES = ["no_loose_match", "attribute_differs", "opposite_direction", "null_mismatch"]
WIN_MARGIN, WIN_NEAR, WIN_NULL = 0.05, 0.02, 0.15


# ------------------------------------------------------------------------------------------------ helpers
def jload(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def f(x, nd: int = 3) -> str:
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def hms(sec: Optional[float]) -> str:
    if sec is None:
        return "—"
    sec = int(sec)
    return f"{sec // 3600:d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def med(xs: List[float]) -> Optional[float]:
    return float(statistics.median(xs)) if xs else None


def tokens_by_doc(d: Path) -> Dict[str, dict]:
    out = {}
    try:
        with open(d / "tokens.csv", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                out[r["doc"]] = {"p": int(r["prompt_tokens"]), "c": int(r["completion_tokens"]), "s": float(r["seconds"])}
    except Exception:  # noqa: BLE001
        pass
    return out


def phases(run: Path) -> List[dict]:
    rows = []
    try:
        for line in (run / "phases.tsv").read_text(encoding="utf-8").splitlines():
            a = line.split("\t")
            if len(a) >= 4:
                rows.append({"name": a[0], "start": float(a[1]), "end": float(a[2]), "status": a[3], "note": a[4] if len(a) > 4 else ""})
    except Exception:  # noqa: BLE001
        pass
    return rows


# ------------------------------------------------------------------------------------------------ phase A
def variant_data(run: Path, name: str) -> Optional[dict]:
    d = run / f"dev_{name}"
    sc = jload(d / "score" / "score.json")
    if not sc or "score" not in sc:
        return None
    return {"dir": d, "raw": sc["score"]["modes"]["raw"], "tokens": tokens_by_doc(d)}


def _row(name: str, label: str, levels: dict, null: dict, lang: Optional[float], finding: Optional[float], tok: Optional[dict]) -> str:
    s, st, lo = levels["standard"], levels["strict"], levels["loose"]
    return (f"| {name} | {label} | {f(s['precision'])} / {f(s['recall'])} / {f(s['f1'])} | {f(st['f1'])} | {f(lo['f1'])} | "
            f"{f(null['precision'])} / {f(null['recall'])} | {f(lang)} | {f(finding)} | "
            f"{f(tok['p'], 0) if tok else '—'} | {f(tok['c'], 0) if tok else '—'} | {f(tok['s'], 0) if tok else '—'} |")


def compare(run: Path) -> Tuple[str, str]:
    data = {n: variant_data(run, n) for n, _ in VARIANTS}
    L: List[str] = ["# Phase A: dev scores, baseline vs Socratic prompt", "",
                    "Gold: Murphy 2005 (gold doc `murphy2005`, corpus slug YKQQZV93) and 4CB9X9XE. Raw mode (duplicate edges not collapsed), "
                    "default object-attribute threshold. Tokens and seconds are per paper from `tokens.csv`; the dev runs bypass the cache, "
                    "so the timings are real.", "",
                    "| variant | paper | standard P / R / F1 | strict F1 | loose F1 | null P / R | causal_language acc | finding recall | "
                    "prompt tok/paper | completion tok/paper | seconds/paper |", "|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|"]
    for name, _ in VARIANTS:
        v = data[name]
        if not v:
            L.append(f"| {name} | (no score: the dev run for this variant failed, see its log) | | | | | | | | | |")
            continue
        raw, tok = v["raw"], v["tokens"]
        used = []
        for gdoc, r in raw["docs"].items():
            t = tok.get(r["pred_doc"])
            used.append(t) if t else None
            L.append(_row(name, gdoc, r["levels"], r["null"], r["pairs"]["causal_language_accuracy"], (r["findings"] or {}).get("recall"), t))
        m = raw["micro"]
        mt = ({"p": statistics.mean(x["p"] for x in used), "c": statistics.mean(x["c"] for x in used),
               "s": statistics.mean(x["s"] for x in used)} if used else None)
        L.append(_row(f"**{name}**", "**micro**", m["levels"], m["null"], m["pairs"]["causal_language_accuracy"],
                      (m["findings"] or {}).get("recall"), mt))
    # error reasons
    L += ["", "## Error reasons", "", "False negatives are gold edges we missed; false positives are our edges with no gold match.", "",
          "| variant | list | " + " | ".join(c.replace("_", " ") for c in CODES) + " | other |", "|---|---|" + "---:|" * (len(CODES) + 1)]
    for name, _ in VARIANTS:
        v = data[name]
        if not v:
            continue
        for lst, key in (("false negatives", "fn"), ("false positives", "fp")):
            c = Counter(x.get("reason_code", "other") for x in v["raw"][key])
            L.append(f"| {name} | {lst} | " + " | ".join(str(c.get(k, 0)) for k in CODES) + f" | {sum(n for k, n in c.items() if k not in CODES)} |")
    # who found what
    b, s = data["baseline"], data["socratic"]
    if b and s:
        def key(x):
            return (x["doc"], x.get("finding"), x["gold_edge"])
        fn_b = {key(x): x for x in b["raw"]["fn"]}
        fn_s = {key(x): x for x in s["raw"]["fn"]}
        for title, only, other in (("Found by baseline, missed by Socratic", fn_s, fn_b), ("Found by Socratic, missed by baseline", fn_b, fn_s)):
            keys = [k for k in only if k not in other]
            L += ["", f"## {title}: {len(keys)} gold edge(s)" + (" (first 15 shown)" if len(keys) > 15 else ""), ""]
            for i, k in enumerate(keys[:15], 1):
                x = only[k]
                L.append(f"{i}. [{x['doc']}{' ' + x['finding'] if x.get('finding') else ''}] `{x['gold']}`  \n   why missed: {x['reason']}")
            if not keys:
                L.append("(none)")
    winner, why = decide(data)
    L += ["", "## Winner", "", f"**{winner}** ({dict(VARIANTS)[winner]}): {why}", "",
          f"Rule: Socratic wins only if its micro standard F1 is at least {WIN_MARGIN} above baseline, or within {WIN_NEAR} of baseline with null recall at "
          f"least {WIN_NULL} higher; otherwise baseline wins."]
    (run / "dev_comparison.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (run / "winner.txt").write_text(dict(VARIANTS)[winner] + "\n", encoding="utf-8")
    return winner, why


def decide(data: Dict[str, Optional[dict]]) -> Tuple[str, str]:
    b, s = data.get("baseline"), data.get("socratic")
    if not b and not s:
        return "baseline", "neither dev run produced a score, so the default (baseline) is used"
    if not s:
        return "baseline", "the Socratic dev run produced no score, so baseline is used by default"
    if not b:
        return "baseline", "the baseline dev run produced no score (the rule cannot be evaluated), so baseline is used by default"
    mb, ms = b["raw"]["micro"], s["raw"]["micro"]
    fb, fs = mb["levels"]["standard"]["f1"], ms["levels"]["standard"]["f1"]
    nb, ns = (mb["null"]["recall"] or 0.0), (ms["null"]["recall"] or 0.0)
    d, dn = fs - fb, ns - nb
    facts = f"micro standard F1 baseline {fb:.3f} vs Socratic {fs:.3f} (difference {d:+.3f}); null recall {nb:.3f} vs {ns:.3f} (difference {dn:+.3f})"
    if d >= WIN_MARGIN - 1e-9:
        return "socratic", f"Socratic F1 is at least {WIN_MARGIN} higher. {facts}"
    if abs(d) <= WIN_NEAR + 1e-9 and dn >= WIN_NULL - 1e-9:
        return "socratic", f"F1 within {WIN_NEAR} and null recall at least {WIN_NULL} higher. {facts}"
    return "baseline", f"Socratic did not meet either condition. {facts}"


# ------------------------------------------------------------------------------------------------ phase D
def full_stats(run: Path, name: str, ph: List[dict]) -> Optional[dict]:
    d = run / f"full_{name}"
    log, gp = jload(d / "run_log.json"), d / "camo_graph.json"
    if not log or not gp.exists():
        return None
    papers = log["papers"]
    ok = [p for p in papers if not p.get("error")]
    bad = [p for p in papers if p.get("error")]
    graph = jload(gp) or {"edges": [], "nodes": []}
    edges_per = Counter(e.get("source_document") for e in graph["edges"])
    docs = [p["doc"] for p in papers]
    per = [edges_per.get(x, 0) for x in docs]
    retries = []
    try:
        with open(d / "retries.csv", encoding="utf-8", newline="") as fh:
            retries = list(csv.DictReader(fh))
    except Exception:  # noqa: BLE001
        pass
    wall = sum(r["end"] - r["start"] for r in ph if r["name"] == f"full_{name}")      # a retry runs inside this phase
    return {
        "dir": d, "papers": len(papers), "ok": len(ok), "failed": bad, "retries": len(retries), "gave_up": sum(1 for r in retries if r.get("gave_up") == "1"),
        "p_tot": sum(p["prompt_tokens"] for p in papers), "c_tot": sum(p["completion_tokens"] for p in papers),
        "p_med": med([p["prompt_tokens"] for p in papers]), "c_med": med([p["completion_tokens"] for p in papers]),
        "wall": wall or None, "edges": len(graph["edges"]), "nodes": len(graph["nodes"]),
        "nulls": sum(1 for e in graph["edges"] if e.get("negated")),
        "epp_med": med(per), "epp_min": min(per) if per else None, "epp_max": max(per) if per else None,
        "zero": [x for x, n in zip(docs, per) if n == 0], "edges_per": {x: n for x, n in zip(docs, per)},
        "validation": jload(d / "validation.json"),
    }


def report(run: Path) -> None:
    ph = phases(run)
    L: List[str] = [f"# Overnight evaluation report", "", f"Run folder: `{run}`  ·  generated {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    cmp_md = run / "dev_comparison.md"
    L += ["## 1. Phase A: baseline vs Socratic on the dev set", ""]
    if cmp_md.exists():
        body = cmp_md.read_text(encoding="utf-8").splitlines()
        L += [("#" + ln) if ln.startswith("#") else ln for ln in body[1:]]
    else:
        L.append("(phase A did not produce dev_comparison.md)")
    stats = {n: full_stats(run, n, ph) for n, _ in VARIANTS}
    L += ["", "## 2. Full runs", ""]
    for name, fname in VARIANTS:
        s = stats[name]
        L += [f"### full_{name} ({fname})", ""]
        if not s:
            L += ["not completed (no output files; see the phase log and section 4).", ""]
            continue
        v = s["validation"] or {}
        L += [f"- papers: **{s['ok']} ok**, **{len(s['failed'])} failed** (of {s['papers']}); retries: {s['retries']} logged ({s['gave_up']} gave up)",
              f"- tokens: total prompt {s['p_tot']:,}, completion {s['c_tot']:,}; per paper median prompt {f(s['p_med'], 0)}, completion {f(s['c_med'], 0)}",
              f"- wall clock: {hms(s['wall'])}",
              f"- graph: {s['edges']:,} edges, {s['nodes']:,} nodes, {s['nulls']:,} null results; edges per paper median {f(s['epp_med'], 1)}, "
              f"min {s['epp_min']}, max {s['epp_max']}",
              f"- validation: YAML {'OK' if v.get('yaml_ok') else 'FAILED' if v else 'not run'}, JSON {'OK' if v.get('json_ok') else 'FAILED' if v else 'not run'} "
              f"({v.get('validators', '—')})"]
        if v.get("errors"):
            L += ["  - " + e[:200] for e in v["errors"][:5]]
        if s["failed"]:
            c = Counter(p["error"][:90] for p in s["failed"])
            L += ["- failures by reason:"] + [f"  - {n}× {r}" for r, n in c.most_common(8)]
            L += ["- failed papers: " + ", ".join(p["doc"] for p in s["failed"][:40]) + (" …" if len(s["failed"]) > 40 else "")]
        L += [f"- papers with 0 edges ({len(s['zero'])}): " + (", ".join(s["zero"][:80]) + (" …" if len(s["zero"]) > 80 else "") if s["zero"] else "none"), ""]
    a, b = stats["baseline"], stats["socratic"]
    if a and b:
        L += ["## 3. Baseline vs Socratic, side by side", "", "| | baseline | socratic |", "|---|---:|---:|"]
        for lab, k in (("papers ok", "ok"), ("papers failed", None), ("edges", "edges"), ("nodes", "nodes"), ("null results", "nulls"),
                       ("edges per paper (median)", "epp_med"), ("papers with 0 edges", None), ("prompt tokens (total)", "p_tot"),
                       ("completion tokens (total)", "c_tot"), ("completion tokens / paper (median)", "c_med"), ("wall clock", None), ("retries", "retries")):
            def val(s):
                if lab == "papers failed":
                    return len(s["failed"])
                if lab == "papers with 0 edges":
                    return len(s["zero"])
                if lab == "wall clock":
                    return hms(s["wall"])
                v = s[k]
                return f"{v:,}" if isinstance(v, int) else f(v, 1)
            L.append(f"| {lab} | {val(a)} | {val(b)} |")
        common = [x for x in a["edges_per"] if x in b["edges_per"]]
        top = sorted(common, key=lambda x: -abs(a["edges_per"][x] - b["edges_per"][x]))[:10]
        L += ["", "Ten papers where the variants differ most in edge count:", "", "| paper | baseline edges | socratic edges | difference |", "|---|---:|---:|---:|"]
        L += [f"| {x} | {a['edges_per'][x]} | {b['edges_per'][x]} | {b['edges_per'][x] - a['edges_per'][x]:+d} |" for x in top]
        L.append("")
    L += ["## 4. Timing and what went wrong", "", "| phase | start | end | duration | status | note |", "|---|---|---|---:|---|---|"]
    for r in ph:
        L.append(f"| {r['name']} | {time.strftime('%H:%M:%S', time.localtime(r['start']))} | {time.strftime('%H:%M:%S', time.localtime(r['end']))} | "
                 f"{hms(r['end'] - r['start'])} | {r['status']} | {r['note']} |")
    bad = [r for r in ph if r["status"] not in ("ok", "skipped")]
    L += ["", "Problems: " + ("; ".join(f"{r['name']}: {r['status']} {r['note']}" for r in bad) if bad else "no phase failed."),
          "Skipped: " + ("; ".join(f"{r['name']}: {r['note']}" for r in ph if r["status"] == "skipped") or "nothing.")]
    (run / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("compare", "report"):
        print(__doc__, file=sys.stderr)
        return 2
    run = Path(argv[1])
    if argv[0] == "compare":
        winner, why = compare(run)
        print(f"winner: {winner}\n{why}")
    else:
        report(run)
        print(f"wrote {run / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
