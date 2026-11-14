"""Step 7: compress statistics parentheticals to [sig] / [ns]; drop +- dispersion terms.

The original sentence is kept in the sidecar so that p-value, significance and analysis method can be
extracted later by regex instead of by the model.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

DEFAULT_ALPHA = 0.05

_NUM = r"[-−–]?\d[\d.,]*"
_PN = r"0?\.\d+(?:[eE][-−]?\d+)?|\d(?:\.\d+)?"
_P = re.compile(rf"(?<![A-Za-z])[Pp](?:[- ]?value)?\s*(?P<op>≤|≥|≪|<=|>=|=|<|>)\s*(?P<val>{_PN})")
_NS = re.compile(r"(?<![A-Za-z])(?:n\.?s\.?|NS)(?![A-Za-z])")

# (name, regex) of recognised test-statistic tokens
_TESTS: List[Tuple[str, re.Pattern]] = [
    ("F", re.compile(rf"(?<![A-Za-z])F\s*(?:\(\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*\)|\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?|\d+)?\s*=\s*{_NUM}")),
    ("t", re.compile(rf"(?<![A-Za-z])t\s*(?:\(\s*\d+\s*\)|\d+)?\s*=\s*{_NUM}")),
    ("chi2", re.compile(rf"(?<![A-Za-z])(?:χ|Χ|X|chi|Chi)(?:-?square[d]?)?\s*[²2]?\s*(?:\(\s*\d+\s*(?:,\s*[Nn]\s*=\s*\d+)?\s*\)|\d+)?\s*=\s*{_NUM}")),
    ("rank", re.compile(rf"(?<![A-Za-z])(?:H|U|W|Z|Q)\s*(?:\(\s*\d+\s*\))?\s*=\s*{_NUM}")),
    ("corr", re.compile(rf"(?<![A-Za-z])(?:r|R|rs|ρ|rho|τ|tau)\s*[²2]?\s*(?:adj\.?)?\s*=\s*{_NUM}")),
    ("df", re.compile(r"(?<![A-Za-z])(?:d\.?f\.?|df)\s*=\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)?")),
]
_N = re.compile(r"(?<![A-Za-z])[nN]\s*=\s*\d+")
_REF = re.compile(r"(?:Fig\.?|Figs\.?|Figure|Table|Tab\.)\s*[A-Z]?\d+[A-Za-z]?(?:\s*(?:[-–,&]|and)\s*[A-Z]?\d+[A-Za-z]?)*", re.I)
_PAREN = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)")   # one level of nesting: F(2, 36)
_ALPHA = re.compile(r"(?:α|alpha)\s*(?:=|of|level of|level)\s*(0?\.\d+)|significance level (?:of|was|at)\s*(0?\.\d+)", re.I)
_PM = re.compile(r"\s*±\s*(?:\d[\d.,]*\s*(?:SE|SD|SEM|s\.e\.m?\.?|s\.d\.)?|(?:SE|SD|SEM|s\.e\.m?\.?|s\.d\.|standard error|standard deviation))(?![A-Za-z])")


def detect_alpha(text: str) -> float:
    for m in _ALPHA.finditer(text):
        v = m.group(1) or m.group(2)
        try:
            a = float(v)
            if 0 < a < 1:
                return a
        except ValueError:
            pass
    return DEFAULT_ALPHA


def p_significance(op: str, val: float, alpha: float) -> Optional[bool]:
    """True = significant, False = not significant, None = cannot tell at this alpha."""
    if op == "=":
        return val < alpha
    if op in ("<", "≪"):
        return True if val <= alpha else None
    if op in ("≤", "<="):
        return True if val <= alpha else None
    if op in (">", "≥", ">="):
        return False if val >= alpha else None
    return None


def _scan_parenthetical(content: str, alpha: float):
    """Return (marker, leftover_refs, record) if the whole parenthetical is statistics, else None."""
    rest = content
    tests = []
    for name, rx in _TESTS:
        for m in rx.finditer(content):
            tests.append((name, m.group()))
        rest = rx.sub(" ", rest)
    ps = [(m.group("op"), m.group("val"), m.group()) for m in _P.finditer(content)]
    rest = _P.sub(" ", rest)
    has_ns = bool(_NS.search(rest))
    rest = _NS.sub(" ", rest)
    rest = _N.sub(" ", rest)
    refs = [m.group().strip() for m in _REF.finditer(rest)]
    rest = _REF.sub(" ", rest)
    rest = re.sub(r"\b(?:and|or|respectively|for|all|both|each)\b", " ", rest)
    rest = re.sub(r"[\s,;:=]+", "", rest)
    if rest:
        return None                          # something we don't understand -> leave unchanged
    if not tests and not ps and not has_ns:
        return None
    sig: Optional[bool] = None
    pv = None
    if ps:
        verdicts = []
        for op, val, _ in ps:
            try:
                v = float(val)
            except ValueError:
                return None
            verdicts.append(p_significance(op, v, alpha))
        if None in verdicts or len(set(verdicts)) != 1:
            return None
        sig = verdicts[0]
        pv = (ps[0][0], float(ps[0][1]))
    elif has_ns:
        sig = False
    else:
        return None                          # test statistic without a p-value: significance unknown
    rec: Dict = {
        "tests": [t for t, _ in tests], "test_text": [t for _, t in tests], "p_op": pv[0] if pv else None,
        "p_value": pv[1] if pv else None, "alpha": alpha, "significance": "significant" if sig else "not_significant",
    }
    return ("[sig]" if sig else "[ns]"), refs, rec


def compress_stats(sent: str, alpha: float = DEFAULT_ALPHA) -> Tuple[str, List[Dict]]:
    """Return (compressed sentence, extracted statistics records)."""
    records: List[Dict] = []
    out, pos = [], 0
    for m in _PAREN.finditer(sent):
        scanned = _scan_parenthetical(m.group(1), alpha)
        if not scanned:
            continue
        marker, refs, rec = scanned
        rec["original"] = m.group()
        records.append(rec)
        out.append(sent[pos:m.start()])
        out.append("(" + "; ".join(refs + [marker]) + ")" if refs else marker)
        pos = m.end()
    out.append(sent[pos:])
    s = "".join(out)
    s2 = _PM.sub("", s)
    if s2 != s:
        records.append({"dispersion_dropped": True})
        s = re.sub(r"\(\s*(?:mean|means|average)?\s*\)", "", s2)
    s = re.sub(r"\s{2,}", " ", re.sub(r"\s+([,.;:)])", r"\1", s)).strip()
    return s, records
