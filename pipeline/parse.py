"""Stage 4a: tolerant parser for the model's one-line-per-claim output.

    F|sentences|CAUSE|predicate|EFFECT[;EFFECT...]|language|design[|key=value...]
    N|sentences|CAUSE|predicate|EFFECT[;EFFECT...]|design[|key=value...]
    CAUSE/EFFECT = thing/property/change[/type]    or, for a management action,  thing/change/type
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

CHANGES = {"+", "-", "=", "pres", "abs", "intro", "rem", "occ"}
_CHANGE_WORDS = {
    "increased": "+", "increase": "+", "increases": "+", "up": "+", "↑": "+", "higher": "+", "greater": "+",
    "decreased": "-", "decrease": "-", "decreases": "-", "reduced": "-", "reduce": "-", "down": "-", "↓": "-", "lower": "-",
    "stable": "=", "unchanged": "=", "same": "=", "equal": "=",
    "present": "pres", "presence": "pres", "absent": "abs", "absence": "abs",
    "introduced": "intro", "introduction": "intro", "removed": "rem", "removal": "rem", "occurred": "occ", "occurrence": "occ",
}
TYPES = {"tax", "var", "com", "proc", "mgmt"}
_TYPE_WORDS = {"taxon": "tax", "species": "tax", "variable": "var", "environmental variable": "var", "env": "var",
               "community": "com", "guild": "com", "composite": "com", "process": "proc", "management": "mgmt",
               "management action": "mgmt", "action": "mgmt", "intervention": "mgmt"}
PREDICATES = {"c", "ct", "p", "e", "d", "a", "cw", "pr"}
_PRED_WORDS = {"causes": "c", "cause": "c", "contributes_to": "ct", "contributes to": "ct", "contributes": "ct", "prevents": "p",
               "prevent": "p", "enables": "e", "enable": "e", "disrupts": "d", "disrupt": "d", "associated_with": "a",
               "associated with": "a", "associated": "a", "correlated_with": "cw", "correlated with": "cw", "correlated": "cw",
               "precedes": "pr", "precede": "pr"}
_LANG = {"d": "D", "direct": "D", "direct_causal": "D", "u": "U", "uncertain": "U", "uncertain_causal": "U", "hedged": "U",
         "a": "A", "associational": "A", "association": "A"}
_DESIGN = {"exp": "exp", "experiment": "exp", "experimental": "exp", "obs": "obs", "observational": "obs", "observation": "obs",
           "rev": "rev", "review": "rev", "meta-analysis": "rev", "meta_analysis": "rev", "meta": "rev", "mod": "mod",
           "model": "mod", "modeling": "mod", "modelling": "mod", "simulation": "mod", "jud": "jud", "judgment": "jud",
           "judgement": "jud", "judgment_call": "jud"}
_LINE_STRICT = re.compile(r"^\s*([FfNn])\s*\|")
_LINE_LENIENT = re.compile(r"^\s*(?:[FfNn]\s*\||[AaUuDd]\s*\|\s*\[?\d)")   # 'A|5|...': the language letter written as the kind


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Var:
    thing: str
    prop: Optional[str] = None
    change: Optional[str] = None          # one of CHANGES
    vtype: Optional[str] = None           # one of TYPES
    parts: Tuple["Var", ...] = ()         # a joint cause ('A;B' in the CAUSE field): one node named 'A and B'

    def key(self, stage: Optional[str] = None) -> Tuple:
        return (norm(self.thing), norm(self.prop), self.change, self.vtype, stage)


@dataclass
class Claim:
    kind: str                             # F | N
    sentences: List[int]
    cause: Var
    predicate: str                        # code
    effects: List[Var]
    language: Optional[str]               # D | U | A | None (always None for N)
    design: str
    keys: Dict[str, str] = field(default_factory=dict)
    raw: str = ""


def norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def change_of(x: Optional[str]) -> Optional[str]:
    x = norm(x)
    if x in CHANGES:
        return x
    return _CHANGE_WORDS.get(x)


def type_of(x: Optional[str]) -> Optional[str]:
    x = norm(x)
    if x in TYPES:
        return x
    return _TYPE_WORDS.get(x)


# Lenient parsing (2026-11-14): a value word the format has no code for ('T2/origin/hatchery-reared', 'pH/high') is kept
# verbatim on the property instead of losing the line; 'kg/ha' is not a field separator; an F line whose language is N is a
# null result; a ';' list of causes is one joint cause.  PIPELINE_STRICT_PARSE=1 restores the old behaviour (comparisons).
LENIENT = os.environ.get("PIPELINE_STRICT_PARSE", "") != "1"
_UNIT_SLASH = re.compile(r"(?<=[\w²³%])\s*/\s*(?=(?:ha|m|m2|m²|m3|m³|km|km2|km²|cm|cm2|mm|yr|year|y|d|day|days|h|hr|s|L|l|g|kg|mg|"
                         r"t|plot|plots|tree|trees|ind|individual|individuals|quadrat|ramet|ramets|month|week|wk|ml|mL|ppm)\b"
                         r"(?![\w(]*\s*/\s*(?:tax|var|com|proc|mgmt)\b))")
_LINE = _LINE_LENIENT if LENIENT else _LINE_STRICT
_NULL_PER_EFFECT = re.compile(r"\|\s*N\s*;\s*", re.I)
_NULL_LANG = {"n", "null", "ns", "none", "no", "no_relationship", "no relationship", "nr", "no effect"}


def _qual(prop: Optional[str], value: str) -> str:
    return f"{prop} ({value})" if prop else value


def parse_var(s: str) -> Optional[Var]:
    v = _parse_var_strict(s)
    if v is not None or not LENIENT:
        return v
    s2 = _UNIT_SLASH.sub(" per ", s)
    v = _parse_var_strict(s2)
    if v is not None:
        return v
    parts = [p.strip() for p in s2.strip().split("/")]
    n = len(parts)
    if not parts[0] or n < 3 or n > 4:
        return None
    thing, a, b = parts[0], parts[1], parts[2]
    vt = type_of(parts[3]) if n == 4 and parts[3] else None
    if n == 4 and parts[3] and vt is None:
        if change_of(parts[3]) and a and b and not change_of(b):    # thing/property/property/change: one property
            return Var(thing, f"{a} {b}", change_of(parts[3]))
        return None
    if change_of(a):                                       # thing/change/<value>: the value describes the thing
        return Var(f"{b} {thing}" if b else thing, None, change_of(a), vt)     # 'late planting(T1)
    return Var(thing, _qual(a or None, b), None, vt)       # thing/property/<value>: value kept on the property


def parse_cause(s: str) -> Optional[Var]:
    """The CAUSE field: one variable, or (lenient) several separated by ';' = one joint cause."""
    v = parse_var(s)
    if v is not None or not LENIENT or ";" not in s:
        return v
    comps = [parse_var(c) for c in s.split(";") if c.strip()]
    if len(comps) < 2 or any(c is None for c in comps):
        return None
    types = {c.vtype for c in comps}
    return Var(" and ".join(c.thing for c in comps), None, None, types.pop() if len(types) == 1 else None, tuple(comps))


def _parse_var_strict(s: str) -> Optional[Var]:
    parts = [p.strip() for p in s.strip().split("/")]
    n = len(parts)
    if not parts or not parts[0] or n > 4:
        return None
    thing = parts[0]
    if n == 1:
        return Var(thing)
    if n == 2:
        x = parts[1]
        if not x:
            return Var(thing)
        if change_of(x):
            return Var(thing, None, change_of(x))
        if type_of(x):
            return Var(thing, None, None, type_of(x))
        return Var(thing, x)
    if n == 3:
        a, b = parts[1], parts[2]
        if a and change_of(a) and (not b or type_of(b)):                 # management form: thing/change/type
            return Var(thing, None, change_of(a), type_of(b) if b else None)
        if change_of(b) or not b:                                         # thing/property/change
            return Var(thing, a or None, change_of(b) if b else None)
        if type_of(b):                                                    # thing/property/type (no change)
            return Var(thing, a or None, None, type_of(b))
        return None
    a, b, c = parts[1], parts[2], parts[3]                                # thing/property/change/type
    if (b and not change_of(b)) or (c and not type_of(c)):
        return None
    return Var(thing, a or None, change_of(b) if b else None, type_of(c) if c else None)


def parse_sentences(s: str) -> List[int]:
    out: List[int] = []
    s = re.sub(r"[\[\]()]", " ", s)
    for tok in re.split(r"[,;\s]+", s.strip()):
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            if b - a <= 60:
                out.extend(range(a, b + 1))
        elif tok.isdigit():
            out.append(int(tok))
    return sorted(set(out))


def _norm_word(x: str) -> str:
    return re.sub(r"\s+", " ", x.strip().lower())


def parse_line(line: str) -> Claim:
    m = _LINE.match(line)
    if not m:
        raise ParseError("not an F| or N| line")
    if LENIENT and line.lstrip()[:1] in "Ff":
        line = _NULL_PER_EFFECT.sub(";", line)               # 'A|N;B|N|exp': every effect marked null -> 'A;B|N|exp'
    parts = [p.strip() for p in line.strip().split("|")]
    kind = parts[0].strip().upper()
    lang_kind = None
    if kind in ("A", "U", "D"):                              # lenient only (_LINE_LENIENT): an F line, kind = its language
        kind, lang_kind = "F", kind
    if len(parts) < 6:
        raise ParseError("too few fields")
    sentences = parse_sentences(parts[1])
    if not sentences:
        raise ParseError("no sentence numbers")
    cause = parse_cause(parts[2])
    if cause is None:
        raise ParseError("cause not parseable")
    pw = _norm_word(parts[3])
    predicate = pw if pw in PREDICATES else _PRED_WORDS.get(pw)
    if not predicate:
        raise ParseError(f"unknown predicate {parts[3]!r}")
    effects = [parse_var(e) for e in parts[4].split(";") if e.strip()]
    if not effects or any(e is None for e in effects):
        raise ParseError("effect not parseable")
    rest = parts[5:]
    language: Optional[str] = None
    if kind == "F" and LENIENT and _norm_word(rest[0]) in _NULL_LANG and len(rest) >= 2:
        kind, rest = "N", rest[1:]                           # 'F|...|N|exp': the model's way of writing a null result
    if kind == "F":
        lw = _norm_word(rest[0])
        if lw in _LANG:
            language = _LANG[lw]
            rest = rest[1:]
        elif _norm_word(rest[0]) in _DESIGN:                 # language missing: the field after the effects is the design
            language = lang_kind
        else:
            raise ParseError(f"unknown language {rest[0]!r}")
    else:
        if len(rest) >= 2 and _norm_word(rest[0]) in _LANG and _norm_word(rest[1]) in _DESIGN:
            rest = rest[1:]                                  # tolerate a language field on an N line
    if not rest:
        raise ParseError("design missing")
    design = _DESIGN.get(_norm_word(rest[0]))
    if not design:
        raise ParseError(f"unknown design {rest[0]!r}")
    keys: Dict[str, str] = {}
    for kv in rest[1:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            k, v = k.strip().lower(), v.strip()
            if k and v:
                keys[k] = v
    return Claim(kind, sentences, cause, predicate, [e for e in effects if e], language, design, keys, line.strip())


def parse_text(text: str) -> Tuple[List[Claim], List[str]]:
    """Return (claims, unparseable F|/N| lines).  Everything else (prose, blank lines, fences) is ignored."""
    claims: List[Claim] = []
    bad: List[str] = []
    for line in (text or "").splitlines():
        if not _LINE.match(line):
            continue
        try:
            claims.append(parse_line(line))
        except ParseError as e:
            log.debug("unparseable line (%s): %s", e, line.strip()[:120])
            bad.append(line.strip())
    return claims, bad


def check_sentences(claims: Iterable[Claim], valid: Iterable[int]) -> Tuple[List[Claim], int]:
    """Drop sentence numbers that do not exist; drop claims left with none.  Returns (claims, number dropped)."""
    ok = set(valid)
    out: List[Claim] = []
    dropped = 0
    for c in claims:
        keep = [n for n in c.sentences if n in ok]
        if not keep:
            dropped += 1
            continue
        c.sentences = keep
        out.append(c)
    return out, dropped
