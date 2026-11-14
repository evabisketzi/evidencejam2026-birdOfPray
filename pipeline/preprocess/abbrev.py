"""Paper-defined abbreviations: 'net ecosystem productivity (NEP)' -> {'NEP': 'net ecosystem productivity'}.

Deterministic, after Schwartz & Hearst (2003), "A simple algorithm for identifying abbreviation definitions in biomedical
text": a short form in parentheses, and the shortest run of preceding words whose letters contain the short form's
characters in order, the first one starting a word.  Only the first definition of each short form is kept."""
from __future__ import annotations

import re
from typing import Dict, Optional

_PAREN = re.compile(r"\(\s*([^()\s,;][^(),;]{0,11}?)\s*(?:[,;][^()]{0,40})?\)")     # '(VMC)', '(VMC, %)'
_STOP = re.compile(r"[.;:!?()\[\]\n]")          # the long form never crosses a sentence / bracket boundary
_SHORT_OK = re.compile(r"^[A-Za-z][A-Za-z0-9\-/]*$")
_NOT_ABBR = {"Fig", "Figs", "Table", "Tab", "Eq", "App", "Appendix", "Supplementary", "Online", "SE", "SD", "CI", "NS",
             "ns", "pers", "comm", "sic", "unpubl", "eds", "ed", "Ltd", "Inc"}


def _is_short_form(s: str) -> bool:
    if not (2 <= len(s) <= 10) or not _SHORT_OK.match(s) or s in _NOT_ABBR:
        return False
    upper = sum(c.isupper() for c in s)
    return upper >= 2 or (upper == 1 and any(c.isdigit() for c in s))     # NEP, GEPmax, SUVA254, CO2; not 'pH', 'site'


def _singular(long: str) -> str:
    if long.endswith("ies"):
        return long[:-3] + "y"
    if re.search(r"(?:ss|x|ch|sh)es$", long) or long.endswith("gases"):
        return long[:-2]
    return long[:-1]


def _best_long_form(short: str, long: str) -> Optional[str]:
    """Schwartz-Hearst backward character match; returns the long form or None."""
    s_i, l_i = len(short) - 1, len(long) - 1
    while s_i >= 0:
        c = short[s_i].lower()
        if not c.isalnum():
            s_i -= 1
            continue
        while l_i >= 0 and (long[l_i].lower() != c or (s_i == 0 and l_i > 0 and long[l_i - 1].isalnum())):
            l_i -= 1
        if l_i < 0:
            return None
        l_i -= 1
        s_i -= 1
    start = long.rfind(" ", 0, l_i + 1) + 1
    return long[start:].strip()


def find_abbreviations(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in _PAREN.finditer(text):
        short = m.group(1).strip()
        if short.endswith("s") and short[:-1].isupper() and len(short) > 2:
            short = short[:-1]                                   # '(PAHs)' defines PAH
        if not _is_short_form(short) or short in out:
            continue
        before = text[max(0, m.start() - 300):m.start()]
        cut = max((mm.end() for mm in _STOP.finditer(before)), default=0)
        words = before[cut:].split()
        n_chars = sum(c.isalnum() for c in short)
        window = words[-min(n_chars + 5, n_chars * 2):]
        if not window:
            continue
        long = _best_long_form(short, " ".join(window))
        if not long:
            continue
        long = re.sub(r"^(?:the|a|an)\s+", "", long, flags=re.I).strip(" ,")
        if m.group(1).strip() != short and long.endswith("s"):
            long = _singular(long)                               # '(PAHs)': 'polycyclic aromatic hydrocarbon' for PAH
        n_words = len(long.split())
        if (len(long) <= len(short) or n_words < 2 and len(long) < 2 * len(short) or short.lower() in long.lower().split()
                or n_words > min(n_chars + 5, n_chars * 2) or not long[:1].isalpha()):
            continue
        ws = long.split()
        if (len(ws) > 1 and ws[0][:1].isupper() and ws[0][1:].islower() and not re.search(r"['’]s$", ws[0])
                and all(not w[:1].isupper() for w in ws[1:])):
            long = long[:1].lower() + long[1:]                   # sentence-initial 'Acid mine drainage'; keeps 'Moss Layer ...'
        out[short] = long
    return out


def expand_abbreviations(s: str, abbrev: Dict[str, str]) -> str:
    """'Soil VMC' -> 'Soil volumetric moisture content (VMC)'.  Only whole tokens, case-sensitive, never twice, never when
    the long form is already written out or the token is already in brackets."""
    if not s or not abbrev:
        return s
    low = s.lower()
    for short in sorted(abbrev, key=len, reverse=True):
        long = abbrev[short]
        if long.lower() in low:
            continue
        rx = re.compile(rf"(?<![\w(\-]){re.escape(short)}(?![\w)\-])")
        for m in rx.finditer(s):
            if s[:m.start()].count("(") > s[:m.start()].count(")"):
                continue                                         # inside brackets: no nested '(... (CT) ...)'
            s = f"{s[:m.start()]}{long} ({short}){s[m.end():]}"
            low = s.lower()
            break
    return s
