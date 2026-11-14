"""python -m pipeline.preprocess.cli corpus/ out/pre/ [--filter] [--context-tokens N] [--jobs N] [--slug X] [--limit N]"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from .assemble import Options, PaperResult, process_paper
from .legend import load_taxon_table
from .tokens import get_counter

log = logging.getLogger("preprocess")

STAGES = [("raw", "raw markdown"), ("clean", "after clean (step 2)"), ("cut", "after cutting sections (3-5)"),
          ("cited", "after citation drop/strip (6)"), ("stats", "after stats compression (7)"),
          ("filter", "after optional filter (10)"), ("final", "final prompt text (11)")]
FIELDS = ["slug", "doi"] + [f"tokens_{k}" for k, _ in STAGES] + [
    "sentences_total", "sentences_kept", "dropped_cited_background", "dropped_filter", "citations_stripped",
    "sections_detected", "fallbacks"]

_G: Dict = {}


def _init(no_download: bool, table_path: Optional[str]) -> None:
    _G["count"], _G["tok"] = get_counter(allow_download=not no_download)
    _G["table"] = load_taxon_table(Path(table_path) if table_path else None)


def _work(args) -> PaperResult:
    path, meta, opts = args
    slug = Path(path).stem
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return process_paper(slug, raw, meta, _G["count"], opts, _G["table"])


def load_index(corpus: Path) -> Dict[str, Dict[str, str]]:
    idx = {}
    p = corpus / "index.csv"
    if p.exists():
        with open(p, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                idx[row["slug"]] = row
    return idx


def summarise(rows: List[Dict], tokenizer: str) -> str:
    out = [f"tokenizer: {tokenizer}", f"papers: {len(rows)}", "",
           f"{'stage':<34}{'total tokens':>14}{'median/paper':>14}{'saved vs prev':>15}{'saved vs raw':>14}"]
    prev = None
    raw_total = sum(int(r["tokens_raw"]) for r in rows) or 1
    for k, label in STAGES:
        vals = [int(r[f"tokens_{k}"]) for r in rows]
        tot = sum(vals)
        sp = "" if prev is None else f"{(1 - tot / prev) * 100:6.1f}%" if prev else ""
        out.append(f"{label:<34}{tot:>14,}{int(statistics.median(vals)):>14,}{sp:>15}{(1 - tot / raw_total) * 100:>13.1f}%")
        prev = tot
    fb: Dict[str, int] = {}
    for r in rows:
        for f in filter(None, r["fallbacks"].split(";")):
            fb[f] = fb.get(f, 0) + 1
    out += ["", "fallbacks used (papers affected):"]
    out += [f"  {k}: {v}" for k, v in sorted(fb.items())] or ["  none"]
    tot_s = sum(int(r["sentences_total"]) for r in rows)
    kept = sum(int(r["sentences_kept"]) for r in rows)
    cb = sum(int(r["dropped_cited_background"]) for r in rows)
    out += ["", f"sentences in kept sections: {tot_s:,}   numbered: {kept:,}   dropped cited_background: {cb:,}   "
                f"citations stripped from kept: {sum(int(r['citations_stripped']) for r in rows):,}"]
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.preprocess.cli")
    ap.add_argument("corpus")
    ap.add_argument("out")
    ap.add_argument("--filter", action="store_true", help="drop sentences with no causal/hedge wording (off by default)")
    ap.add_argument("--context-tokens", type=int, default=400)
    ap.add_argument("--max-legend", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--slug", action="append", help="only these slugs")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--taxon-table")
    ap.add_argument("--no-download", action="store_true", help="never try to download the Qwen tokenizer")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    corpus, out = Path(a.corpus), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = load_index(corpus)
    files = sorted(corpus.glob("*.md"))
    if a.slug:
        files = [f for f in files if f.stem in set(a.slug)]
    if a.limit:
        files = files[: a.limit]
    opts = Options(filter=a.filter, context_tokens=a.context_tokens, max_legend=a.max_legend)
    jobs = [(str(f), index.get(f.stem, {}), opts) for f in files]

    rows: List[Dict] = []
    _init(a.no_download, a.taxon_table)
    tokenizer = _G["tok"]
    if a.jobs > 1 and len(jobs) > 4:
        with ProcessPoolExecutor(a.jobs, initializer=_init, initargs=(a.no_download, a.taxon_table)) as ex:
            results = ex.map(_work, jobs, chunksize=4)
            for r in results:
                _write(out, r)
                rows.append(r.report)
    else:
        for j in jobs:
            r = _work(j)
            _write(out, r)
            rows.append(r.report)
    for r in rows:
        r["tokenizer"] = tokenizer
    with open(out / "report.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + ["tokenizer"])
        w.writeheader()
        w.writerows(rows)
    print(summarise(rows, tokenizer))
    return 0


def _write(out: Path, r: PaperResult) -> None:
    (out / f"{r.slug}.txt").write_text(r.txt, encoding="utf-8")
    (out / f"{r.slug}.json").write_text(json.dumps(r.sidecar, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
