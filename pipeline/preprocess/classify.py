"""Step 6: find citations, find own-study cues, decide keep / strip / drop for each sentence."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

# ----------------------------------------------------------------------------- citation grammar
_AUTH = r"(?:(?:de|van|von|der|den|la|le|du|del|di|da|dos|ter)\s+)?[A-ZÀ-Þ][\w'’\-]+"
_AUTHORS = (rf"{_AUTH}(?:\s+(?:and|&)\s+{_AUTH}|\s+et\s+al\.?|,\s+{_AUTH}(?:,?\s+(?:and|&)\s+{_AUTH})?)?")
_YEAR1 = r"(?:1[89]|20)\d\d[a-z]?"
_YEARS = rf"{_YEAR1}(?:\s*[,–\-]\s*(?:{_YEAR1}|[a-z](?![a-z])))*"
_LEAD = re.compile(r"^(?:(?:e\.g\.|i\.e\.|see(?: also)?|cf\.|but see|reviewed in|reviewed by|for review see|for reviews? see|"
                   r"also|compare|in|following|after|by|from|using|sensu|as in|as per)(?:(?<=\.)|\b)\s*,?\s*)+", re.I)
_CITE_PART = re.compile(rf"^{_AUTHORS},?\s*(?:\(?{_YEARS}\)?|in press|submitted|unpublished)(?P<tail>.*)$", re.S)
_TAIL_OK = re.compile(r"^[\s,;:.\dp–\-a-z()]{0,24}$")
_PAREN = re.compile(r"\(([^()]*)\)")
_FIRST_EXCL = {"In", "The", "On", "Table", "Fig", "Figure", "Year", "Since", "By", "During", "Between", "After", "Before",
               "Until", "Winter", "Spring", "Summer", "Fall", "Autumn", "June", "July", "May", "April", "March",
               "August", "September", "October", "November", "December", "January", "February", "Day", "Week",
               "Month", "Plot", "Site", "Block", "Treatment", "Group", "Experiment", "Study", "Phase", "Stage"}
_INLINE = re.compile(rf"(?<![\w(])({_AUTHORS})\s*,?\s*\(\s*{_YEARS}(?:\s*[;,]\s*{_YEARS})*\s*\)")
_INLINE_BARE = re.compile(rf"(?<![\w(])((?:{_AUTH}\s+(?:and|&)\s+{_AUTH}|{_AUTH}\s+et\s+al\.?)),?\s*{_YEARS}(?![\w\d])")
_NUMBERED = re.compile(r"\s*\[\s*\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*\s*\]")


@dataclass
class Citation:
    start: int
    end: int
    kind: str       # paren | inline | numbered
    text: str
    repl: str = ""


def _is_cite_part(part: str) -> bool:
    p = part.strip()
    if not p:
        return False
    p = _LEAD.sub("", p).strip()
    m = _CITE_PART.match(p)
    if not m:
        return False
    first = re.match(r"[A-ZÀ-Þa-z][\w'’\-]*", p)
    if first and first.group() in _FIRST_EXCL:
        return False
    return bool(_TAIL_OK.match(m.group("tail")))


def find_citations(sent: str) -> List[Citation]:
    out: List[Citation] = []
    taken: List[Tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    # 1. parenthetical author-year groups
    for m in _PAREN.finditer(sent):
        content = m.group(1)
        if not re.search(r"(?:1[89]|20)\d\d|in press", content):
            continue
        parts = [x for x in re.split(r";", content)]
        flags = [_is_cite_part(x) for x in parts]
        if not any(flags):
            continue
        keep = [x.strip() for x, f in zip(parts, flags) if not f and x.strip()]
        a = m.start()
        while a > 0 and sent[a - 1] == " ":
            a -= 1
        if keep:
            out.append(Citation(m.start(), m.end(), "paren", m.group(), "(" + "; ".join(keep) + ")"))
        else:
            out.append(Citation(a, m.end(), "paren", m.group(), ""))
        taken.append((out[-1].start, out[-1].end))

    # 2. inline "Smith (2003)", "Lee et al. (2010)"
    for m in _INLINE.finditer(sent):
        if m.group(1).split()[0] in _FIRST_EXCL or not free(m.start(), m.end()):
            continue
        out.append(Citation(m.start(), m.end(), "inline", m.group(), "[ref]"))
        taken.append((m.start(), m.end()))
    # 2b. bare "Lee et al. 2010", "Smith and Jones 2003"
    for m in _INLINE_BARE.finditer(sent):
        if m.group(1).split()[0] in _FIRST_EXCL or not free(m.start(), m.end()):
            continue
        out.append(Citation(m.start(), m.end(), "inline", m.group(), "[ref]"))
        taken.append((m.start(), m.end()))

    # 3. numbered references
    for m in _NUMBERED.finditer(sent):
        if free(m.start(), m.end()):
            out.append(Citation(m.start(), m.end(), "numbered", m.group().strip(), ""))
            taken.append((m.start(), m.end()))
    out.sort(key=lambda c: c.start)
    return out


def strip_citations(sent: str, cites: Sequence[Citation]) -> str:
    if not cites:
        return sent
    pieces, pos = [], 0
    for c in cites:
        pieces.append(sent[pos:c.start])
        pieces.append(c.repl)
        pos = c.end
    pieces.append(sent[pos:])
    return tidy("".join(pieces))


def tidy(s: str) -> str:
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s+([,.;:!?)])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"([,;])\s*([,;.])", r"\2", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


# ----------------------------------------------------------------------------- own-study cues
_OWN_WORDS = re.compile(r"\b(?:my|we|our|ours|myself|ourselves)\b", re.I)
_I = re.compile(r"(?<![A-Za-z'’\-])I(?:\s+[a-z]+|’[a-z]+|'[a-z]+)")
_I_LABEL = re.compile(r"\b(?:type|phase|class|group|stage|table|fig|figure|appendix|step|zone|level|order|category|"
                      r"cluster|model|treatment|site|plot|block|axis|component|factor|cohort)\s+I\b", re.I)
_OWN_PHRASES = re.compile(
    r"\b(?:this|the present|the current|present|current)\s+(?:study|experiment|paper|work|research|analysis|article|"
    r"survey|investigation|trial|project|restoration|manuscript)\b"
    r"|\bthese\s+(?:results|data|findings|observations|patterns|analyses|experiments|trends)\b"
    r"|\bthe\s+(?:results|findings)\s+(?:of\s+(?:this|the present)|suggest|indicate|show|demonstrate)\b"
    r"|\b(?:here|herein)\b(?:,|\s+(?:we|I)\b)"
    r"|\bin\s+(?:my|our)\s+(?:plots?|sites?|experiment|study|data|stands?|plantations?|treatments?)\b"
    r"|\b(?:the\s+)?results\s+(?:suggest|indicate|show|demonstrate)\b",
    re.I,
)
RESULT_WORDS = {"increase", "increased", "increases", "decrease", "decreased", "decreases", "reduced", "reduce", "reduces",
                "higher", "lower", "greater", "fewer", "significant", "significantly", "suppressed", "suppress", "affected",
                "differed", "declined", "promoted", "inhibited", "killed", "enhanced", "dominated", "correlated"}


_OWN_FLOAT = re.compile(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Tab\.)\s*[A-Z]?\d")


def has_own_cue(sent: str, species_forms: Iterable[str] = ()) -> bool:
    # a pointer to this paper's own figure/table ("... (Fig. 3; Smith 1999)") marks an own result
    if _OWN_WORDS.search(sent) or _OWN_PHRASES.search(sent) or _OWN_FLOAT.search(sent):
        return True
    for m in _I.finditer(sent):
        # "I" as a roman numeral / label is excluded
        if not _I_LABEL.search(sent[max(0, m.start() - 15): m.end()]):
            return True
    forms = [f for f in species_forms if len(f) >= 4]
    if forms and any(f in sent for f in forms):
        words = {w.lower() for w in re.findall(r"[A-Za-z]+", sent)}
        if words & RESULT_WORDS:
            return True
    return False


# ----------------------------------------------------------------------------- decision
@dataclass
class Decision:
    keep: bool
    reason: str                     # kept | cited_background | own_cue_stripped
    text: str                       # sentence after citation stripping (== input if none)
    citations: List[str] = field(default_factory=list)
    own_cue: bool = False


def classify_sentence(sent: str, species_forms: Iterable[str] = ()) -> Decision:
    cites = find_citations(sent)
    own = has_own_cue(sent, species_forms)
    if not cites:
        return Decision(True, "kept", sent, [], own)
    texts = [c.text for c in cites]
    if own:
        return Decision(True, "own_cue_stripped", strip_citations(sent, cites), texts, True)
    return Decision(False, "cited_background", sent, texts, False)
