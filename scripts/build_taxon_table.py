#!/usr/bin/env python3
"""Build data/ncbitaxon_names.tsv (name<TAB>taxid) from an NCBI taxdump.

Only names that occur in the corpus are kept, so the committed table stays small.  The dump itself is
not committed.  Usage:

    curl -O https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
    mkdir taxdump && tar -xzf taxdump.tar.gz -C taxdump names.dmp nodes.dmp
    python scripts/build_taxon_table.py --names taxdump/names.dmp --nodes taxdump/nodes.dmp \
        --corpus corpus/ --out data/ncbitaxon_names.tsv

Selection rule when a name maps to several taxa: scientific name > equivalent name > genbank synonym >
synonym; species/subspecies/variety ranks first; plants, fungi, invertebrates and vertebrates before
bacteria/viruses/unassigned; then the lowest taxid.  Deterministic.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CLASS_PRI = {"scientific name": 0, "equivalent name": 1, "genbank synonym": 2, "synonym": 3}
RANK_PRI = {"species": 0, "subspecies": 1, "varietas": 1, "forma": 2, "species group": 3, "species subgroup": 3, "hybrid": 1}
DIV_PRI = {4: 0, 1: 0, 10: 0, 2: 0, 5: 0, 6: 0, 8: 2, 11: 3, 0: 4, 9: 5, 3: 5, 7: 5}
BINOM = re.compile(r"\b([A-Z][a-z]{2,})\s+((?:×\s*)?[a-z]{3,})\b")
GENUS = re.compile(r"\b([A-Z][a-z]{3,})\b")


def corpus_candidates(corpus: Path) -> set[str]:
    cands: set[str] = set()
    for p in sorted(corpus.glob("*.md")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r"[*_]|<[^>]+>", "", txt)
        for g, e in BINOM.findall(txt):
            cands.add(f"{g} {e}")
    return cands


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True)
    ap.add_argument("--nodes", required=True)
    ap.add_argument("--corpus", default="corpus")
    ap.add_argument("--out", default="data/ncbitaxon_names.tsv")
    a = ap.parse_args()

    cands = corpus_candidates(Path(a.corpus))
    print(f"{len(cands):,} candidate binomials in the corpus", file=sys.stderr)

    best: dict[str, tuple] = {}
    hits: dict[int, list] = {}
    with open(a.names, encoding="utf-8") as f:
        for line in f:
            parts = [x.strip() for x in line.rstrip("\n").split("|")]
            if len(parts) < 4:
                continue
            taxid, name, cls = int(parts[0]), parts[1], parts[3]
            if cls in CLASS_PRI and name in cands:
                hits.setdefault(taxid, []).append((name, cls))
    rank, div = {}, {}
    need = set(hits)
    with open(a.nodes, encoding="utf-8") as f:
        for line in f:
            parts = [x.strip() for x in line.split("|")]
            t = int(parts[0])
            if t in need:
                rank[t], div[t] = parts[2], int(parts[4])
    for taxid, lst in hits.items():
        for name, cls in lst:
            key = (CLASS_PRI[cls], RANK_PRI.get(rank.get(taxid, ""), 9), DIV_PRI.get(div.get(taxid, 8), 3), taxid)
            if name not in best or key < best[name][0]:
                best[name] = (key, taxid)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("name\ttaxid\n")
        for name in sorted(best):
            f.write(f"{name}\t{best[name][1]}\n")
    print(f"wrote {len(best):,} names -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
