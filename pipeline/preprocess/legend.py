"""Step 9: species legend.

Scans the whole cleaned text (including the sections that get cut, but not the reference list) for
binomials, abbreviated binomials, "hereafter X" definitions, "Full name (ABBR)" definitions and common
names given next to a binomial.  Variants are grouped into one entry; NCBITaxon ids come from
``data/ncbitaxon_names.tsv`` when available.  The article text itself keeps its original names.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = ROOT / "data" / "ncbitaxon_names.tsv"

_STOP_GENERA = {"The", "This", "These", "Those", "That", "There", "Their", "They", "When", "Where", "While", "With", "Within",
                "From", "Table", "Figure", "Fig", "Total", "Mean", "Number", "Percent", "Density", "Cover", "Species", "Plot",
                "Site", "Study", "Data", "Results", "Methods", "Spring", "Summer", "Autumn", "Winter", "Early", "Late",
                "North", "South", "East", "West", "Lake", "River", "Forest", "Mount", "Initial", "Final", "Control", "Treatment"}
_STOP_EPITHETS = {"and", "the", "was", "were", "with", "that", "from", "for", "are", "has", "had", "not", "but", "this", "which",
                  "than", "then", "also", "both", "each", "such", "into", "over", "under", "between", "among", "during", "after",
                  "before", "while", "since", "using", "used", "about", "per", "via", "can", "may", "will", "have", "been", "its"}
_RANK = r"(?:var\.|subsp\.|ssp\.|f\.)"
_BINOM = re.compile(rf"\b([A-Z][a-z]{{2,}})\s+(?:×\s*)?([a-z]{{3,}})(?:\s+{_RANK}\s+[a-z]{{3,}})?\b")
_ABBR_BINOM = re.compile(r"\b([A-Z])\.\s?([a-z]{3,})\b")
_ITALIC_RAW = [
    re.compile(r"(?<!\*)\*{1,2}(?!\*)([A-Z][a-z]{2,}\s+(?:×\s*)?[a-z]{3,}(?:\s+" + _RANK + r"\s+[a-z]{3,})?)\*{1,2}"),
    re.compile(r"<(?:i|em)>\s*([A-Z][a-z]{2,}\s+(?:×\s*)?[a-z]{3,}(?:\s+" + _RANK + r"\s+[a-z]{3,})?)\s*</(?:i|em)>"),
    re.compile(r"(?<![\w])_([A-Z][a-z]{2,}\s+[a-z]{3,})_(?![\w])"),
]
_HEREAFTER = re.compile(r"\(\s*(?:hereafter|hereinafter|henceforth)[,:]?\s*(?:referred to as\s*|called\s*)?[\"“']?([^)\"”']{1,30}?)[\"”']?\s*\)", re.I)
_STOPWORDS = {"the", "of", "a", "an", "and", "in", "by", "for", "with", "on", "to", "as", "or", "at", "from", "is", "are", "was", "were", "that", "this"}


@dataclass
class Species:
    name: str                      # full binomial
    variants: List[str] = field(default_factory=list)
    taxid: Optional[int] = None
    count: int = 0
    group: bool = False            # a group word (rodents, grasses) from data/taxon_groups.tsv, not a species of the paper


def load_taxon_table(path: Optional[Path] = None) -> Dict[str, int]:
    path = Path(path) if path else DEFAULT_TABLE
    table: Dict[str, int] = {}
    if not path.exists():
        return table
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 2 and row[0] != "name":
                try:
                    table[row[0].lower()] = int(row[1])
                except ValueError:
                    pass
    return table


def italic_binomials(raw: str) -> List[str]:
    found: List[str] = []
    for rx in _ITALIC_RAW:
        for m in rx.finditer(raw):
            found.append(re.sub(r"\s+", " ", m.group(1)).replace("× ", "×"))
    return found


def _plausible(genus: str, epithet: str) -> bool:
    return genus not in _STOP_GENERA and epithet not in _STOP_EPITHETS


def build_legend(raw: str, cleaned_text: str, used_text: str, table: Optional[Dict[str, int]] = None,
                 max_entries: int = 25) -> List[Species]:
    """`cleaned_text`: where to look for definitions; `used_text`: the text that will be shown to the model
    (entries not occurring there are dropped)."""
    table = table or {}
    # drop reference list from the scan
    scan = re.split(r"\n#*\s*\**(?:References|Literature Cited|LITERATURE CITED|Bibliography)\**\s*\n", cleaned_text)[0]
    full: "OrderedDict[str, Species]" = OrderedDict()

    def add(name: str) -> None:
        name = re.sub(r"\s+", " ", name.strip())
        if name not in full:
            full[name] = Species(name)

    for nm in italic_binomials(raw):
        g, e = nm.split()[:2]
        if _plausible(g, e):
            add(nm.split(" var.")[0].split(" subsp.")[0].split(" ssp.")[0].split(" f.")[0])
    if table:
        for m in _BINOM.finditer(scan):
            g, e = m.group(1), m.group(2)
            if _plausible(g, e) and f"{g} {e}".lower() in table:
                add(f"{g} {e}")
    if not full:
        return []

    by_abbr: Dict[Tuple[str, str], List[str]] = {}
    for name in full:
        g, e = name.split()[:2]
        by_abbr.setdefault((g[0], e), []).append(name)

    # abbreviated binomials -> unique full binomial with same initial + epithet
    abbr_forms: Dict[str, str] = {}
    for m in _ABBR_BINOM.finditer(scan):
        cands = by_abbr.get((m.group(1), m.group(2)))
        if cands:
            abbr_forms[f"{m.group(1)}. {m.group(2)}"] = cands[0]
    for ab, nm in abbr_forms.items():
        full[nm].variants.append(ab)

    for name, sp in full.items():
        g, e = name.split()[:2]
        pat = re.escape(g) + r"\s+" + re.escape(e)
        # "Full name (ABBR)" and "(hereafter X)" definitions
        for m in re.finditer(pat + r"[^()]{0,60}?\(([^()]{1,40})\)", scan):
            inner = m.group(1).strip()
            h = _HEREAFTER.match("(" + inner + ")")
            if h:
                sp.variants.append(h.group(1).strip())
            elif re.fullmatch(r"[A-Z][A-Za-z]{1,7}", inner) and len(re.findall(rf"\b{re.escape(inner)}\b", scan)) >= 2:
                sp.variants.append(inner)
            elif re.fullmatch(r"[a-z][a-z\- ]{2,30}", inner) and len(inner.split()) <= 3 and inner.split()[0] not in _STOPWORDS:
                sp.variants.append(inner)
        # common name immediately before "(Genus species)"
        for m in re.finditer(r"((?:[A-Za-z][A-Za-z\-]*\s+){1,3})\(\s*" + pat, scan):
            words = m.group(1).split()
            for n in (3, 2, 1):
                if len(words) < n:
                    continue
                cand = " ".join(words[-n:])
                if cand.split()[0].lower() in _STOPWORDS or any(w.lower() in _STOPWORDS for w in cand.split()):
                    continue
                if cand[0].isupper() and n == 1:
                    continue
                if len(re.findall(re.escape(cand), scan, flags=re.I)) >= 2:
                    sp.variants.append(cand)
                    break
        sp.taxid = table.get(name.lower())

    # keep only species that actually occur in the text shown to the model
    out: List[Species] = []
    for sp in full.values():
        forms = [sp.name] + sp.variants
        sp.count = sum(len(re.findall(r"(?<![\w])" + re.escape(f) + r"(?![\w])", used_text)) for f in forms)
        # dedupe variants preserving order
        seen, vs = set(), []
        for v in sp.variants:
            if v not in seen and v != sp.name:
                seen.add(v)
                vs.append(v)
        sp.variants = vs
        if sp.count > 0:
            out.append(sp)
    out.sort(key=lambda s: (-s.count, s.name))
    return out[:max_entries]


GROUPS_TABLE = ROOT / "data" / "taxon_groups.tsv"
_groups_cache: Dict[str, List[Tuple[str, int, List[str]]]] = {}


def load_taxon_groups(path: Optional[Path] = None) -> List[Tuple[str, int, List[str]]]:
    """(scientific name, NCBITaxon id, word forms) per group; IDs checked by hand against NCBI Taxonomy."""
    path = Path(path) if path else GROUPS_TABLE
    key = str(path)
    if key not in _groups_cache:
        rows: List[Tuple[str, int, List[str]]] = []
        if path.exists():
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.reader(f, delimiter="\t"):
                    if len(row) >= 3 and row[1].isdigit():
                        rows.append((row[0], int(row[1]), [w.strip() for w in row[2].split(",") if w.strip()]))
        _groups_cache[key] = rows
    return _groups_cache[key]


def group_entries(used_text: str, legend: List[Species], max_entries: int = 8, min_count: int = 2,
                  path: Optional[Path] = None) -> List[Species]:
    """--taxon-groups: legend entries for group words the paper uses ("rodents", "grasses").  The entry keeps the paper's
    word as its name; the ID is the group's.  A group is skipped when a legend species already carries the word (a paper
    whose "willow" is Salix bebbiana) or belongs to the group's genus."""
    taken = " ; ".join(f for sp in legend for f in [sp.name] + sp.variants).lower()
    genera = {sp.name.split()[0].lower() for sp in legend}
    out: List[Species] = []
    for sci, taxid, forms in load_taxon_groups(path):
        if sci.lower() in genera:
            continue
        found = []
        for f in forms:
            n = len(re.findall(r"(?<![\w-])" + re.escape(f) + r"(?![\w-])", used_text, flags=re.I))
            if n:
                found.append((n, f))
        total = sum(n for n, _ in found)
        if total < min_count or any(re.search(r"(?<![\w-])" + re.escape(f) + r"(?![\w-])", taken) for _, f in found):
            continue
        found.sort(key=lambda x: -x[0])
        out.append(Species(found[0][1], [f for _, f in found[1:]], taxid, total, True))
    out.sort(key=lambda s: (-s.count, s.name))
    return out[:max_entries]


def species_forms(legend: Iterable[Species]) -> List[str]:
    """Forms usable for own-study / filter matching (binomials and abbreviations only)."""
    forms = []
    for sp in legend:
        if sp.group:
            continue
        forms.append(sp.name)
        forms.extend(v for v in sp.variants if re.fullmatch(r"[A-Z]\. [a-z]+", v))
    return forms


def format_legend(legend: List[Species]) -> str:
    parts = []
    for i, sp in enumerate(legend, 1):
        v = f" ({', '.join(sp.variants)})" if sp.variants else ""
        parts.append(f"T{i}={sp.name}{v}")
    return "; ".join(parts)
