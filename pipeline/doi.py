"""DOI fallback for articles whose DOI cell in index.csv is empty: look in the first lines of the article's markdown.

Rules: first 40 lines; skip lines naming a data repository (dryad, zenodo, figshare, pangaea) and reference-list lines;
prefer matches in the first 15 lines; trailing punctuation and markdown/URL wrapping are stripped; the DOI is used only if exactly
one distinct candidate remains.  The index.csv DOI always wins.

    python -m pipeline.doi corpus/ [--out doi_report.csv]        (no LLM: prints what the fallback recovers)
"""
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SEARCH_LINES = 40
PREFER_LINES = 15
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>\])]+", re.I)
_REPO = re.compile(r"dryad|zenodo|figshare|pangaea", re.I)
_REFLINE = re.compile(r"^\s*(?:[-*•]\s+|\[\d+\]\s*|\d+\.\s+)")
_YEAR = re.compile(r"\b(?:19|20)\d\d\b")
_TRAIL = ".,;:*_'\"”’)]}>&"


@dataclass(frozen=True)
class DoiInfo:
    doi: str
    source: str                 # index | markdown | none
    line: Optional[int] = None


def clean_candidate(c: str) -> str:
    c = c.strip()
    while c and c[-1] in _TRAIL:
        c = c[:-1]
    return c


def _is_reference_line(line: str) -> bool:
    return bool(_REFLINE.match(line)) and bool(_YEAR.search(line))


def candidates(lines: Sequence[str]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for i, line in enumerate(list(lines)[:SEARCH_LINES], 1):
        if _REPO.search(line) or _is_reference_line(line):
            continue
        for m in _DOI.finditer(line):
            c = clean_candidate(m.group())
            if len(c) > 8 and "/" in c:
                out.append((i, c))
    return out


def find_doi(lines: Sequence[str]) -> Tuple[Optional[str], Optional[int]]:
    """(doi, line number) or (None, None) when there is no candidate or more than one distinct candidate."""
    cands = candidates(lines)
    early = [c for c in cands if c[0] <= PREFER_LINES]
    pool = early or cands
    distinct = {c.lower() for _, c in pool}
    if len(distinct) != 1:
        return None, None
    line, doi = pool[0]
    return doi, line


def resolve(row: Dict[str, str], corpus: Path) -> DoiInfo:
    idx = (row.get("doi") or "").strip()
    if idx:
        return DoiInfo(idx, "index")
    p = corpus / f"{row['slug']}.md"
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            lines = [next(f, "") for _ in range(SEARCH_LINES)]
    except OSError:
        return DoiInfo("", "none")
    doi, line = find_doi(lines)
    return DoiInfo(doi, "markdown", line) if doi else DoiInfo("", "none")


def resolve_all(rows: Sequence[Dict[str, str]], corpus: Path) -> Dict[str, DoiInfo]:
    out = {r["slug"]: resolve(r, corpus) for r in rows}
    for slug, d in out.items():
        if d.source != "index":
            log.info("doi %s: %s%s", slug, d.source, f" line {d.line}: {d.doi}" if d.source == "markdown" else "")
    return out


def counts(infos: Dict[str, DoiInfo]) -> Dict[str, int]:
    c = Counter(d.source for d in infos.values())
    return {"index": c.get("index", 0), "markdown": c.get("markdown", 0), "none": c.get("none", 0)}


def write_report(path, rows: Sequence[Dict[str, str]], infos: Dict[str, DoiInfo]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", "doi", "source", "line_number"])
        for r in rows:
            d = infos[r["slug"]]
            w.writerow([r["slug"], d.doi, d.source, d.line if d.line else ""])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.doi", description="Show what the markdown DOI fallback recovers (no LLM).")
    ap.add_argument("corpus")
    ap.add_argument("--out", help="write the full report csv here")
    ap.add_argument("--sample", type=int, default=5)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    corpus = Path(a.corpus)
    with open(corpus / "index.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("slug")]
    infos = resolve_all(rows, corpus)
    missing = [r["slug"] for r in rows if not (r.get("doi") or "").strip()]
    got = [s for s in missing if infos[s].source == "markdown"]
    print(f"index.csv rows: {len(rows)}; DOI missing in index.csv: {len(missing)}; recovered from markdown: {len(got)}; still none: {len(missing) - len(got)}")
    rnd = random.Random(a.seed)
    for s in rnd.sample(got, min(a.sample, len(got))):
        d = infos[s]
        line = (corpus / f"{s}.md").read_text(encoding="utf-8", errors="replace").splitlines()[d.line - 1]
        print(f"  {s}: {d.doi}   (line {d.line}) {line.strip()[:150]!r}")
    print("still none: " + (", ".join(s for s in missing if infos[s].source == "none") or "(none)"))
    if a.out:
        write_report(a.out, rows, infos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
