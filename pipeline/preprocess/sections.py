"""Steps 3-4: detect sections, then decide what to keep."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .textmap import Mapped

# squashed (letters only, lower-case) heading text -> section code
_HEADINGS: Dict[str, str] = {}


def _reg(code: str, *names: str) -> None:
    for n in names:
        _HEADINGS[re.sub(r"[^a-z]", "", n.lower())] = code


_reg("abs", "Abstract", "Summary", "Synopsis", "Abstract and keywords")
_reg("int", "Introduction", "Background", "General introduction")
_reg("met", "Methods", "Method", "Materials and Methods", "Material and Methods", "Methodology",
     "Methods and materials", "Study Site", "Study Sites", "Study Area", "Study Areas", "Study region",
     "Site description", "Study site and methods", "Study area and methods", "Experimental procedures")
_reg("res", "Results", "Result", "Results and Discussion", "Results and discussions", "Findings")
_reg("dis", "Discussion", "General discussion")
_reg("con", "Conclusions", "Conclusion", "Concluding remarks", "Summary and conclusions",
     "Implications for Practice", "Management Implications", "Implications for management",
     "Implications for restoration", "Conclusions and management implications",
     "Conclusions and implications", "Practical implications", "Conservation implications",
     "Synthesis and applications", "Synthesis", "Management recommendations",
     "Implications for conservation", "Implications for restoration practice")
_reg("lim", "Limitations", "Limitations of the study", "Study limitations", "Caveats")
_reg("ack", "Acknowledgements", "Acknowledgments", "Acknowledgement", "Acknowledgment", "Funding",
     "Declaration of competing interest", "Declaration of Competing Interests", "Author contributions",
     "Authors' contributions", "Conflict of interest", "Conflicts of interest", "Data availability",
     "Data availability statement", "CRediT authorship contribution statement", "Ethics statement",
     "Competing interests", "Disclosure statement", "Funding sources", "Financial support",
     "Declaration of interests", "Author information", "About the authors", "Notes")
_reg("ref", "References", "Reference", "Literature Cited", "Bibliography", "Works cited",
     "Literature cited", "References and notes", "Cited literature", "Literature")
_reg("sup", "Supplementary", "Supplementary data", "Supplementary material", "Supplementary materials",
     "Supporting information", "Appendix", "Appendices", "Appendix A Supplementary data",
     "Supplemental material", "Online supplementary material")
_reg("figs", "Tables", "Figures", "Figure captions", "Figure legends", "Table captions", "Figure legend",
     "Captions", "Legends")
_reg("noise", "Article info", "Research article", "Original article", "Original paper", "Article", "Research paper",
     "Table of contents", "List of tables", "List of figures", "Contents", "Keywords", "Key words",
     "Highlights", "Graphical abstract", "Short communication", "Review", "Research", "Paper")

CAPTION_RE = re.compile(r"^\s*(?:Table|TABLE|Tab\.|Figure|FIGURE|Fig\.|FIG\.|Figs\.)\s*[A-Z]?\d+[A-Za-z]?\s*[.:|\-–—]\s*\S")
_NUMBERING = re.compile(r"^\s*(?:\(?\d+(?:\.\d+)*[.)]?|[IVXivx]+[.)]|[A-H][.)])\s+")
_LEAD = re.compile(r"^[#\s*_>]+")


def heading_text(par: str) -> Tuple[str, bool]:
    """Return (heading text without markup, was_markdown_heading)."""
    s = par.strip()
    md = s.startswith("#")
    s = _LEAD.sub("", s)
    s = s.rstrip("*_ ").strip()
    s = _NUMBERING.sub("", s)
    s = s.rstrip(":.").strip()
    return s, md


def heading_code(par: str) -> Optional[str]:
    """Section code if this paragraph is a recognised heading, else None."""
    s, md = heading_text(par)
    if not s or len(s) > 90 or "\n" in s:
        return None
    key = re.sub(r"[^a-z]", "", s.lower())
    return _HEADINGS.get(key)


def is_heading(par: str) -> bool:
    s = par.strip()
    if s.startswith("#"):
        return True
    return heading_code(par) is not None and len(s) < 90


def is_caption(par: str) -> bool:
    return bool(CAPTION_RE.match(par)) and not par.lstrip().startswith("#")


@dataclass
class Para:
    start: int           # offsets in the cleaned text
    end: int
    text: str
    kind: str            # heading | subheading | caption | body
    section: str = ""    # code assigned by the state machine
    keep: bool = False
    tag: str = ""        # abs/res/dis/con/lim/cap when kept


@dataclass
class SectionResult:
    paras: List[Para]
    sections_detected: List[str] = field(default_factory=list)
    fallbacks: List[str] = field(default_factory=list)
    intro_aims: str = ""
    methods: List[Para] = field(default_factory=list)


_TABLE_NOTE = re.compile(
    r"\s*(?:Note|Notes|Source|Abbreviations?)\s*[:.]|\s*(?:Tests|Test|Values|Means?|Data|Letters|Asterisks|Superscripts|"
    r"Significance|Standard errors?|Entries|Numbers)\b.{0,80}?\b(?:are|were|followed|indicate[sd]?|denote[sd]?|represent|shown|"
    r"given|reported|based)\b", re.I)
_TAG = {"abs": "abs", "res": "res", "dis": "dis", "con": "con", "lim": "lim"}
_CAPTION_DROP_IN = {"int", "met", "ack", "sup"}

_CITE_SHAPED = re.compile(
    r"""^\s*(?:[-*•]\s*)?(?:\[?\d{1,3}[\].)]\s*)?
        (?:[A-Z][\w'’\-]+,\s+(?:[A-Z]\.?[\s\-]*){1,4}.{0,400}?\b(?:1[89]|20)\d\d[a-z]?\b
          |[A-Z][\w'’\-]+\s+[A-Z]{1,3}[,.].{0,400}?\b(?:1[89]|20)\d\d\b)""",
    re.X,
)


def split_paragraphs(text: str) -> List[Tuple[int, int]]:
    out = []
    pos = 0
    for m in re.finditer(r"\n{2,}", text):
        if m.start() > pos:
            out.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        out.append((pos, len(text)))
    return out


# ----------------------------------------------------------------------------- fuzzy headings
_STAGE = {"front": 0, "abs": 1, "int": 2, "met": 3, "res": 4, "dis": 5, "con": 6, "lim": 7, "ack": 8, "ref": 9, "sup": 9, "figs": 9}
_METHODS_START = ("studysite", "studyarea", "experimentaldesign", "sitedescription", "fieldsite", "samplingdesign",
                  "datacollection", "statisticalanalys", "dataanalys", "fieldmethods", "laboratory", "studyspecies",
                  "studysystem", "studydesign", "materials")


def heading_code_fuzzy(par: str, current: str) -> Optional[str]:
    """Looser mapping for markdown headings such as 'Analysis and Results'.  Only accepted when it moves
    forward through the paper, so 'Methods of analysis' inside Results cannot pull us back to Methods."""
    s, md = heading_text(par)
    if not md or not s or len(s.split()) > 7:
        return None
    key = re.sub(r"[^a-z]", "", s.lower())
    code = None
    if "reference" in key or "literaturecited" in key or "bibliograph" in key:
        code = "ref"
    elif "acknowledg" in key:
        code = "ack"
    elif "discussion" in key:
        code = "res" if "result" in key else "dis"
    elif "result" in key and not key.startswith(("effect", "factor")):
        code = "res"
    elif "conclusion" in key or "implication" in key or "recommendation" in key:
        code = "con"
    elif "method" in key or key.startswith(_METHODS_START):
        code = "met"
    elif "introduction" in key:
        code = "int"
    elif "abstract" in key:
        code = "abs"
    if code and _STAGE[code] >= _STAGE.get(current, 0):
        return code
    return None


_METHODSISH = re.compile(
    r"method|material|sampl|data|analys|statistic|design|site|area|study|procedure|survey|collect|measure|experiment|"
    r"treatment|protocol|search|inclusion|selection|screening|eligib|background|introduction|objective|aim|hypothes|"
    r"literature|scope|framework|definition|terminology|motivation|purpose|rationale", re.I)


def _assign(paras: List[Para], non_imrad: bool) -> List[str]:
    cur = "front"
    seen: List[str] = []
    for p in paras:
        if p.kind in ("heading", "subheading"):
            code = heading_code(p.text)
            if code is None:
                code = heading_code_fuzzy(p.text, cur)
            if code and code != "noise":
                cur = code
                p.kind = "heading"
                if not seen or seen[-1] != code:
                    seen.append(code)
            elif code == "noise" and cur in ("front", "abs") and re.fullmatch(r"key\s*words?", heading_text(p.text)[0], re.I):
                cur = "int"      # the keyword line closes the abstract; what follows is the (unheaded) introduction
            elif non_imrad and p.kind == "subheading" and cur in ("int", "met"):
                s, _ = heading_text(p.text)
                if s and not _METHODSISH.search(s):
                    cur = "res"       # body of a review / essay without Results & Discussion headings
                    if not seen or seen[-1] != "res":
                        seen.append("res")
        p.section = cur
    return seen


# ----------------------------------------------------------------------------- front matter
_FRONT_JUNK = re.compile(
    r"brought to you for free|follow this and additional works|digitalcommons|recommended citation|scholarone|"
    r"\bmanuscripts?\s*$|^part of the .{0,80}commons|permanent link|for more information, please contact|"
    r"^\s*\[?traduit par|^\s*(?:résumé|resume|zusammenfassung|resumen)\s*[:.]", re.I)
_FRENCH = set("le la les des du une un et est sont dans pour par sur avec aux qui que ces cette ont été entre sont au "
              "ainsi leur leurs peut peuvent plus mais ou où donc".split())
_LABEL = re.compile(r"\b(?:Abstract|ABSTRACT|Summary|SUMMARY)\s*[:.\-—–]\s*")


def looks_like_names(t: str) -> bool:
    """Author / affiliation / title-case lines: nearly every word capitalised, no real sentence."""
    words = re.findall(r"[A-Za-zÀ-ÿ'’\-]+", t)
    if len(words) < 2 or len(words) > 45:
        return False
    caps = sum(1 for w in words if w[0].isupper()) / len(words)
    return caps >= 0.75 and len(re.findall(r"[.!?](?:\s|$)", t)) <= 1


def _front_abstract_paragraph(p: Para) -> bool:
    """Decide whether a pre-heading paragraph is abstract-like prose; trims an inline 'Abstract:' label."""
    t = p.text
    if _FRONT_JUNK.search(t) or _CITE_SHAPED.match(t):
        return False
    m = _LABEL.search(t[:700])
    if m:
        p.start += m.end()
        p.text = t = t[m.end():]
    words = re.findall(r"[A-Za-zÀ-ÿ']+", t)
    if len(t) < 200 or len(words) < 30:
        return False
    low = [w.lower() for w in words]
    if sum(1 for w in low if w in _FRENCH) / len(low) > 0.10:
        return False
    caps = sum(1 for w in words if w[0].isupper()) / len(words)
    if caps > 0.35:
        return False                       # author / affiliation list
    return len(re.findall(r"[.!?](?:\s|$)", t)) >= 2


def detect_sections(cleaned: Mapped, title: str = "") -> SectionResult:
    text = cleaned.s
    paras: List[Para] = []
    for a, b in split_paragraphs(text):
        t = text[a:b]
        if not t.strip():
            continue
        if is_caption(t):
            kind = "caption"
        elif is_heading(t):
            kind = "heading" if heading_code(t) else "subheading"
        else:
            kind = "body"
        paras.append(Para(a, b, t, kind))
    res = SectionResult(paras)

    seen = _assign(paras, non_imrad=False)
    if not any(c in seen for c in ("res", "dis")):
        # no Results/Discussion headings at all: re-run treating unrecognised body headings as the body
        for p in paras:
            if p.kind == "heading" and heading_code(p.text) is None:
                p.kind = "subheading"
        seen = _assign(paras, non_imrad=True)
        if "res" in seen:
            res.fallbacks.append("no_results_heading")
    res.sections_detected = seen
    body_codes = [c for c in seen if c in ("abs", "int", "met", "res", "dis", "con", "lim")]
    has_abs = "abs" in seen
    no_headings = not body_codes

    # --- trailing reference block heuristic (when there is no References heading) ---
    if "ref" not in seen:
        run = 0
        for p in reversed(paras):
            if p.kind != "body":
                if run:
                    break
                continue
            if _CITE_SHAPED.match(p.text):
                run += 1
            else:
                break
        if run >= 5:
            body_idx = [i for i, p in enumerate(paras) if p.kind == "body"]
            for i in body_idx[-run:]:
                paras[i].section = "ref"
            res.fallbacks.append("refs_heuristic")

    if no_headings:
        res.fallbacks.append("no_headings")
    elif not has_abs and any(p.section == "front" and p.kind == "body" for p in paras):
        res.fallbacks.append("front_as_abstract")

    # --- table footnotes ("Tests were based on...") directly after a table caption are not claims ---
    for prev, p in zip(paras, paras[1:]):
        if prev.kind == "caption" and re.match(r"\s*(?:Table|TABLE|Tab\.)", prev.text) and p.kind == "body" \
                and _TABLE_NOTE.match(p.text):
            p.kind = "footnote"

    # --- decide keep / tag ---
    for p in paras:
        sec = p.section
        if p.kind in ("heading", "subheading", "footnote"):
            p.keep = False
            continue
        if p.kind == "caption":
            if sec in _CAPTION_DROP_IN:
                continue
            p.keep, p.tag = True, "cap"
            continue
        if no_headings and sec != "ref":
            p.keep, p.tag = True, "res"
        elif sec in _TAG:
            if looks_like_names(p.text) or (len(p.text) < 700 and _CITE_SHAPED.match(p.text)):
                continue                                   # author line / reference string inside a kept section
            p.keep, p.tag = True, _TAG[sec]
        elif sec == "front" and not has_abs and not no_headings:
            if _front_abstract_paragraph(p):
                p.keep, p.tag = True, "abs"
        # int, met, ack, ref, sup, figs, front-with-abstract: dropped (body)

    # --- pieces kept for the background block ---
    intro = [p for p in paras if p.section == "int" and p.kind == "body"]
    if intro:
        aims = intro[-1].text
        if len(aims) < 150 and len(intro) > 1:
            aims = intro[-2].text + " " + aims
        res.intro_aims = aims
    res.methods = [p for p in paras if p.section == "met" and p.kind == "body"]
    return res
