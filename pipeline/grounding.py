"""Stage 2: grounding.  Names -> NCBITaxon IDs; words -> ontology IDs, but only IDs a human has verified."""
from __future__ import annotations

import csv
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
TAXON_TABLE = ROOT / "data" / "ncbitaxon_names.tsv"
TERMS_TABLE = ROOT / "data" / "terms.tsv"


@lru_cache(maxsize=2)
def _taxa(path: str = str(TAXON_TABLE)) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    exact: Dict[str, str] = {}
    lower: Dict[str, str] = {}
    binom: Dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        log.warning("taxon table %s not found: all taxa stay free text", p)
        return exact, lower, binom
    with open(p, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 2 or row[0] == "name" or not row[1].isdigit():
                continue
            exact[row[0]] = row[1]
            lower.setdefault(row[0].lower(), row[1])
            w = row[0].lower().split()
            if len(w) >= 2:
                binom.setdefault(f"{w[0]} {w[1]}", row[1])
    return exact, lower, binom


def taxon_id(name: Optional[str], path: str = str(TAXON_TABLE)) -> Optional[str]:
    """`NCBITaxon:<id>` for a scientific name: exact, then case-insensitive, then genus + epithet without authority."""
    if not name:
        return None
    exact, lower, binom = _taxa(path)
    if not exact:
        return None
    n = re.sub(r"\s+", " ", str(name)).strip()
    tid = exact.get(n) or lower.get(n.lower())
    if not tid:
        w = re.sub(r"[()×]", " ", n).lower().split()
        if len(w) >= 2:
            tid = binom.get(f"{w[0]} {w[1]}")
    return f"NCBITaxon:{tid}" if tid else None


@lru_cache(maxsize=2)
def _terms(path: str = str(TERMS_TABLE)) -> Tuple[Dict[Tuple[str, str], str], List[dict]]:
    verified: Dict[Tuple[str, str], str] = {}
    rows: List[dict] = []
    p = Path(path)
    if not p.exists():
        return verified, rows
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rows.append(r)
            # only rows with an ID that a human marked verified=yes ever produce an ID; an empty curie stays free text
            if (r.get("verified") or "").strip().lower() == "yes" and (r.get("curie") or "").strip():
                verified[((r.get("kind") or "").strip().lower(), r["synonym"].strip().lower())] = r["curie"].strip()
    return verified, rows


def term_id(text: Optional[str], kind: str, path: str = str(TERMS_TABLE)) -> Optional[str]:
    """A CURIE for `text`, only from rows marked verified=yes.  Anything else stays free text."""
    if not text:
        return None
    return _terms(path)[0].get((kind, re.sub(r"\s+", " ", str(text)).strip().lower()))


def unverified_terms(path: str = str(TERMS_TABLE)) -> List[dict]:
    return [r for r in _terms(path)[1] if (r.get("verified") or "").strip().lower() != "yes" or not (r.get("curie") or "").strip()]
