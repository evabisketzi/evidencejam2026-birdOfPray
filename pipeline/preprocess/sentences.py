"""Step 5: ecology-aware sentence splitter.

A boundary is a ., ! or ? (plus closing brackets/quotes) followed by whitespace and then something that
can start a sentence.  Each candidate is then vetoed if the period belongs to an abbreviation, an
initial, a figure/table label, or sits inside an open parenthesis.  Lower-case continuations
("A. petiolata", "S. canadensis") are never candidates in the first place.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Always an abbreviation (never ends a sentence), compared lower-case without the trailing period.
ABBR_ALWAYS = {
    "e.g", "i.e", "cf", "ca", "approx", "vs", "spp", "sp", "subsp", "var", "ssp", "sensu", "viz", "al",
    "dr", "mr", "mrs", "ms", "prof", "inc", "ltd", "ph.d", "a.s.l", "m.a.s.l", "resp", "cv", "aff",
    "nov", "fl", "syn", "auct", "ined", "pers", "unpubl", "comm", "ibid", "cit", "agg",
}
# Abbreviations that are only labels when a number/identifier follows ("Fig. 3", "Table S2", "No. 5").
ABBR_BEFORE_NUMBER = {"fig", "figs", "table", "tab", "eq", "eqs", "no", "nos", "p", "pp", "vol", "app", "appendix",
                      "sect", "chap", "ch", "suppl", "supp", "ref", "refs", "sec", "pl", "plate"}
MONTHS = {"jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
# Words that, as the one-letter "initial" label of a treatment/plot, are followed by a real new sentence.
LABEL_WORDS = {"plot", "site", "treatment", "group", "block", "area", "zone", "stand", "class", "type", "phase",
               "stage", "cluster", "vitamin", "level", "line", "population", "pool", "pond", "transect", "quadrat",
               "sample", "region", "habitat", "patch", "unit", "stratum", "layer", "scenario", "model", "option",
               "table", "figure", "fig", "appendix", "plots", "sites", "treatments", "groups", "blocks", "season",
               "year", "step", "species", "genotype", "cultivar", "variant", "series", "grade", "category", "form"}
STARTERS = {"The", "This", "These", "Those", "In", "It", "We", "I", "A", "An", "However", "Thus", "Our", "Although",
            "Because", "For", "On", "At", "Overall", "Similarly", "There", "Most", "Many", "Some", "All", "None",
            "Here", "Both", "Each", "Several", "Other", "Such", "Therefore", "Moreover", "Additionally", "Also"}
GEO_ABBR = {"u.s", "u.k", "u.s.a", "e.u"}   # "U.S. Forest Service" vs "... in the U.S. The ..."

_CAND = re.compile(r"""([.!?]+)(["'”’)\]]*)(\s+)(?=["“‘'(\[]?[A-Z0-9α-ωΑ-Ω])""")
_TOK = re.compile(r"([A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ.]*[A-Za-zÀ-ɏ])?)$")
_CAPTION_LABEL = re.compile(r"^(?:Figure|Fig|Table|Tab|Eq|Plate|Appendix)s?\.?\s+[A-Z]?\d+[A-Za-z]?$")
_NEXT_WORD = re.compile(r"[\"“‘'(\[]*([A-Za-z0-9α-ωΑ-Ω][\w\-']*)")
_WORD_BEFORE = re.compile(r"([A-Za-z][A-Za-z'’\-]+)\s+$")


def _paren_depth(text: str, start: int, end: int) -> int:
    seg = text[start:end]
    return seg.count("(") - seg.count(")") + seg.count("[") - seg.count("]")


def _is_boundary_vetoed(text: str, p: int, nxt: int, sent_start: int) -> bool:
    """p = index of the final punctuation char of the candidate; nxt = start of the following text."""
    ch = text[p]
    # inside an unclosed parenthesis whose closer is near: "(see Table 2. Results ...)" is not a boundary
    if _paren_depth(text, sent_start, p) > 0:
        close = text.find(")", nxt, nxt + 150)
        if close != -1 and "(" not in text[nxt:close]:
            return True
    if ch != ".":
        return False
    before = text[:p]
    if _CAPTION_LABEL.match(text[sent_start:p]):                       # "Figure 1. Leafing ..." / "Fig. 3. ..."
        return True
    m = _TOK.search(before)
    tok = m.group(1) if m else ""
    low = tok.lower()
    if not tok:
        return False
    after = text[nxt:nxt + 40]
    if low == "al" and before.endswith(("et al", "et. al")):
        return True
    if low in ABBR_ALWAYS and low != "al":
        return True
    if low in ABBR_BEFORE_NUMBER and re.match(r"[\"“(\[]?[A-Z]?\d", after):
        return True
    if low in MONTHS and re.match(r"\d", after):
        return True
    if low in GEO_ABBR:
        nw = _NEXT_WORD.match(after)
        return not (nw and nw.group(1) in STARTERS)
    if re.fullmatch(r"(?:[A-Za-z]\.){1,3}[A-Za-z]", tok) and tok.lower() not in GEO_ABBR:
        return True                                         # compact initials: "A.Y.", "R.J.", "D.D."
    # initials: "S. D. Murphy", "Stephen D. Murphy"
    if len(tok) == 1 and tok.isupper():
        if re.match(r"[A-Z]\.", after) or re.search(r"(?:^|[\s(])[A-Z]\.\s+$", before[:-1]):
            return True
        if re.search(r"[A-Z]\.\s+[A-Z][a-z]+\s+(?:and|&)\s+$", before[:-1]):   # "S. D. Murphy and J. Smith"
            return True
        wb = _WORD_BEFORE.search(before[:-1])
        if wb and wb.group(1)[0].isupper() and wb.group(1).lower() not in LABEL_WORDS:
            nw = _NEXT_WORD.match(after)
            if nw and nw.group(1)[0].isupper() and len(nw.group(1)) >= 2 and nw.group(1) not in STARTERS:
                return True
    return False


def split_spans(text: str) -> List[Tuple[int, int]]:
    """Sentence (start, end) spans in `text` (whitespace trimmed)."""
    spans: List[Tuple[int, int]] = []
    start = 0
    for m in _CAND.finditer(text):
        p = m.end(1) - 1
        nxt = m.end(3)
        if _is_boundary_vetoed(text, p, nxt, start):
            continue
        end = m.end(2)
        if end > start:
            spans.append((start, end))
        start = nxt
    if start < len(text):
        spans.append((start, len(text)))
    out = []
    for a, b in spans:
        seg = text[a:b]
        a2 = a + (len(seg) - len(seg.lstrip()))
        b2 = b - (len(seg) - len(seg.rstrip()))
        if b2 > a2:
            out.append((a2, b2))
    return out


def split_sentences(text: str) -> List[str]:
    return [text[a:b] for a, b in split_spans(text)]


def naive_spans(text: str) -> List[Tuple[int, int]]:
    """Fallback splitter used if the main one fails: split on . ! ? followed by space + capital."""
    out, start = [], 0
    for m in re.finditer(r"[.!?][\"')\]]*\s+(?=[A-Z0-9])", text):
        out.append((start, m.start() + 1))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    return [(a, b) for a, b in out if text[a:b].strip()]
