"""Step 2: remove PDF-to-markdown conversion artefacts, keeping a map to the raw text."""
from __future__ import annotations

import html
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from .sections import heading_code, is_caption, is_heading
from .textmap import Edit, Mapped

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------- patterns
_ESC = re.compile(r"\\([$%&#_{}~])")
_STRAY_LT = re.compile(r"&lt;/?[A-Za-z]{1,6}\s*(?:&gt;|>)")
_ENTITY = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,8}|#\d{1,6}|#[xX][0-9A-Fa-f]{1,6});")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_IMAGE = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)|<img\b[^>]*>|data:image/[A-Za-z+.\-]+;base64,[A-Za-z0-9+/=]{100,}", re.I)
_SUP_CITE = re.compile(r"<sup>\s*(\d+(?:\s*[,–\-]\s*\d+)+)\s*</sup>")
_MATH = re.compile(r"\$([^$\n]{1,80}?)\$")
_LATEX_CMD = {r"\times": "×", r"\pm": "±", r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\chi": "χ",
              r"\alpha": "α", r"\beta": "β", r"\mu": "µ", r"\%": "%", r"\sim": "~", r"\approx": "≈", r"\degree": "°",
              r"\circ": "°", r"\rho": "ρ", r"\eta": "η", r"\omega": "ω", r"\ ": " ", r"\,": " ", r"\;": " "}


def _math_repl(mo: "re.Match") -> str:
    body = mo.group(1)
    if not re.search(r"[\\^_{}]", body):
        return mo.group(0)                    # looks like a dollar amount, not math
    for k, v in _LATEX_CMD.items():
        body = body.replace(k, v)
    body = re.sub(r"\\(?:mathrm|text|mathit|rm)\s*\{([^}]*)\}", r"\1", body)
    body = re.sub(r"[\^_]\s*\{([^}]*)\}", r"\1", body)
    body = re.sub(r"[\^_]\s*(\S)", r"\1", body)
    return re.sub(r"[{}]", "", body).strip()


_LATEX_SUP = re.compile(r"\s*\$\s*[\^_]\s*\{?([^}$\n]{1,12})\}?\s*\$")
_BLOCKTAG = re.compile(r"</?(?:br|p|div|tr|td|th|li|ul|ol|table|thead|tbody|h\d)\b[^<>]{0,100}>", re.I)
_TAG = re.compile(r"</?[A-Za-z][^<>\n]{0,120}>")
_MDLINK = re.compile(r"\[([^\]\n]*)\]\((?:#|https?:|mailto:|www\.)[^)\n]*\)")
_EMPH = re.compile(r"(\*{1,3})(?=\S)([^*\n]+?)(?<=\S)\1")
_UEMPH = re.compile(r"(?<![\w])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w])")

_URL = re.compile(r"(?:https?://|www\.)[^\s<>\]\)]+|\bdoi:\s*\S+|\b10\.\d{4,9}/[^\s<>\]\)]+", re.I)
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")

_PAGENO = re.compile(r"^\s*(?:page\s+)?\d{1,4}\s*(?:of\s*\d+)?\s*$|^\s*[-–—]\s*\d{1,4}\s*[-–—]\s*$|^\s*\d{1,4}\s*/\s*\d{1,4}\s*$", re.I)
_BOILER = re.compile(
    r"downloaded from|terms and conditions|wiley online library|onlinelibrary|sciencedirect|all rights reserved|"
    r"creative commons|this is an open access|journal homepage|contents lists available|"
    r"^\s*©|^\s*copyright|\bissn\b|elsevier|springer|taylor\s*&\s*francis|crossmark|check for updates|"
    r"^\s*(?:received|accepted|revised|available online|published online|article history|handling editor|"
    r"co-?ordinating editor|associate editor)\b|"
    r"^\s*(?:key\s*words?|keywords?)\s*[:\-–]|"
    r"address correspondence|corresponding author|^\s*\W*correspondence\b|^\s*\W*e-?mail\b|"
    r"^\s*\W*(?:cite this article|to cite this article)",
    re.I,
)
_SUPMARK = r"[¹²³⁴⁵⁶⁷⁸⁹⁰*†‡§#\d]"
_AFF_WORD = (r"(?:Department|Dept\.?|Departamento|Institut|Institute|Instituto|Faculty|Faculté|School|College|"
             r"Universit\w*|Centre|Center|Laborator\w*|Ministry|Museum|Academy|Division|CSIRO|Natural Resources|"
             r"Research Station|Forest Service|Environment Canada|Service|Agency|Agriculture)")
_AFF_START = re.compile(rf"^\s*{_SUPMARK}{{0,3}}\s*{_AFF_WORD}\b")
_AFF_ANY = re.compile(rf"{_AFF_WORD}\b")
_SPACED = re.compile(r"^(?:#+\s*)?(?:[A-Za-z]\s){4,}[A-Za-z]\s*$")

_STOP_RIGHT = {"and", "or", "to", "nor", "but", "vs", "versus", "through", "in", "of", "the", "a", "an", "with",
               "for", "by", "at", "on", "as", "from", "than", "not", "is", "are", "was", "were"}
_TERMINAL = ".?!"
_CLOSERS = ")]\"'”’"


@dataclass
class CleanResult:
    cleaned: Mapped
    fallbacks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------------- helpers
def _re_edits(m: Mapped, rx: re.Pattern, fn: Callable[[re.Match], List[Edit]]) -> Mapped:
    edits: List[Edit] = []
    for mo in rx.finditer(m.s):
        edits.extend(fn(mo))
    return m.edit(edits) if edits else m


def _lines(s: str) -> List[Tuple[int, int]]:
    """(start, end) of each line, end excluding the newline."""
    out, pos = [], 0
    for ln in s.split("\n"):
        out.append((pos, pos + len(ln)))
        pos += len(ln) + 1
    return out


def slice_mapped(m: Mapped, a: int, b: int) -> Mapped:
    return Mapped(m.s[a:b], m.idx[a:b])


def concat_mapped(parts: List[Mapped]) -> Mapped:
    s, idx = [], []
    for p in parts:
        s.append(p.s)
        idx.extend(p.idx)
    return Mapped("".join(s), idx)


def _sep(like: Mapped, text: str) -> Mapped:
    """A separator string mapped to the position of `like`'s last char."""
    base = like.idx[-1] + 1 if like.idx else 0
    return Mapped(text, [base] * len(text))


# ----------------------------------------------------------------------------- step A: markup
def strip_markup(m: Mapped) -> Mapped:
    m = _re_edits(m, _COMMENT, lambda mo: [(mo.start(), mo.end(), " ")])
    m = _re_edits(m, _ESC, lambda mo: [(mo.start(), mo.start() + 1, "")])
    m = _re_edits(m, _IMAGE, lambda mo: [(mo.start(), mo.end(), "")])
    # numbered-citation superscripts become a bracket marker the classifier understands
    m = _re_edits(m, _SUP_CITE, lambda mo: [(mo.start(), mo.end(), "[" + re.sub(r"\s+", "", mo.group(1)) + "]")])
    m = _re_edits(m, _MATH, lambda mo: [(mo.start(), mo.end(), _math_repl(mo))] if _math_repl(mo) != mo.group(0) else [])
    m = _re_edits(m, _LATEX_SUP, lambda mo: [(mo.start(), mo.end(), mo.group(1).strip())])
    m = _re_edits(m, _BLOCKTAG, lambda mo: [(mo.start(), mo.end(), " ")])
    m = _re_edits(m, _TAG, lambda mo: [(mo.start(), mo.end(), "")])
    # converter artefact: "<sup>&</sup>lt;sup>1" leaves a literal "&lt;sup>" once the tags are gone
    m = _re_edits(m, _STRAY_LT, lambda mo: [(mo.start(), mo.end(), "")])
    m = _re_edits(m, _ENTITY, lambda mo: [(mo.start(), mo.end(), html.unescape(mo.group()))])
    m = _re_edits(m, _MDLINK, lambda mo: [(mo.start(), mo.start() + 1, ""), (mo.start(1) + len(mo.group(1)), mo.end(), "")])
    m = _re_edits(m, _EMPH, lambda mo: [(mo.start(1), mo.end(1), ""), (mo.end(2), mo.end(), "")])
    m = _re_edits(m, _UEMPH, lambda mo: [(mo.start(), mo.start() + 1, ""), (mo.end() - 1, mo.end(), "")])
    return m


# ----------------------------------------------------------------------------- step B: line-level drops
def _norm_line(ln: str) -> str:
    return re.sub(r"\d", "0", re.sub(r"[#*|\s_]+", " ", ln.lower())).strip()


def _is_table_row(ln: str) -> bool:
    s = ln.strip()
    if not s:
        return False
    pipes = s.count("|")
    if pipes >= 2 and (s.startswith("|") or s.endswith("|") or pipes >= 3):
        return True
    if re.fullmatch(r"[\s:\-|+=]+", s) and "-" in s and len(s) > 3:
        return True
    toks = s.split()
    if len(toks) >= 4:
        num = sum(1 for t in toks if re.fullmatch(r"[-−+±(]?\d[\d.,]*[%)a-z]{0,2}", t))
        if num / len(toks) >= 0.7:
            return True
    return False


def drop_lines(m: Mapped, front_end: int) -> Mapped:
    s = m.s
    lines = _lines(s)
    texts = [s[a:b] for a, b in lines]
    counts = Counter(_norm_line(t) for t in texts if t.strip())
    edits: List[Edit] = []
    for i, ((a, b), t) in enumerate(zip(lines, texts)):
        st = t.strip()
        if not st:
            continue
        drop = False
        if heading_code(t) in {"abs", "int", "met", "res", "dis", "con", "ref", "ack"}:
            continue  # never drop section headings
        if re.match(r"^\s*\W*(?:key\s*words?|keywords?)\s*[:\-–]", t, re.I):
            edits.append((a, b, "#### Keywords"))   # not text, but it marks the end of the abstract
            continue
        n = _norm_line(t)
        if counts[n] >= 3 and 3 <= len(n) <= 200 and not is_caption(t):
            drop = True  # running header / footer / banner
        elif _PAGENO.match(t) or _BOILER.search(t) or _SPACED.match(t):
            drop = True
        elif _is_table_row(t):
            drop = True
        elif _AFF_START.match(t) and (t.count(",") >= 1 or _EMAIL.search(t)):
            drop = True
        elif i <= front_end and _AFF_ANY.search(t) and t.count(",") >= 2 and len(st) < 400:
            drop = True
        elif i <= front_end and _EMAIL.search(t):
            drop = True
        if drop:
            edits.append((a, b, ""))
            continue
        # URL / DOI / email spans inside a kept line
        spans = []
        for mo in list(_URL.finditer(t)) + list(_EMAIL.finditer(t)):
            e = mo.end()
            while e > mo.start() and t[e - 1] in ".,;:)]":
                e -= 1
            spans.append((a + mo.start(), a + e))
        if spans:
            rest = t
            for x, y in sorted(spans, reverse=True):
                rest = rest[: x - a] + rest[y - a:]
            if len(re.findall(r"[A-Za-z]{2,}", rest)) < 3:
                edits.append((a, b, ""))
            else:
                edits.extend((x, y, "") for x, y in spans)
    return m.edit(edits) if edits else m


# ----------------------------------------------------------------------------- step C: whitespace / paragraphs
def normalise_whitespace(m: Mapped) -> Mapped:
    s = m.s
    edits: List[Edit] = []
    # spaces/tabs: collapse, and strip around newlines
    for mo in re.finditer(r"[ \t\u00a0\u2009\u202f]*\n[ \t\u00a0]*|[ \t\u00a0\u2009\u202f]{2,}", s):
        g = mo.group()
        if "\n" in g:
            edits.append((mo.start(), mo.end(), "\n" * min(2, g.count("\n")) if g.count("\n") >= 2 else "\n"))
        else:
            edits.append((mo.start(), mo.end(), " "))
    m = m.edit(edits)
    # runs of newlines -> exactly one blank line
    m = _re_edits(m, re.compile(r"\n{3,}"), lambda mo: [(mo.start(), mo.end(), "\n\n")])
    # single newline between prose lines is a soft wrap; keep it only before headings/bullets/captions
    s = m.s
    edits = []
    for mo in re.finditer(r"(?<!\n)\n(?!\n)", s):
        prev_start = s.rfind("\n", 0, mo.start()) + 1
        prev = s[prev_start: mo.start()]
        nxt_end = s.find("\n", mo.end())
        nxt = s[mo.end(): nxt_end if nxt_end != -1 else len(s)]
        if prev.lstrip().startswith("#") or nxt.lstrip().startswith(("#", "- ", "* ", "• ")) or is_caption(nxt) or is_caption(prev):
            edits.append((mo.start(), mo.end(), "\n\n"))
        else:
            edits.append((mo.start(), mo.end(), " "))
    m = m.edit(edits)
    a = len(m.s) - len(m.s.lstrip("\n"))
    b = len(m.s.rstrip("\n"))
    return Mapped(m.s[a:b], m.idx[a:b])


def _unfinished(t: str) -> bool:
    t = t.rstrip()
    if len(t) < 25:
        return False
    if t[-1] in _TERMINAL:
        return False
    if t[-1] in _CLOSERS and len(t) > 1 and t[-2] in _TERMINAL:
        return False
    return True


def merge_paragraphs(m: Mapped) -> Mapped:
    """Re-join sentences that the PDF converter split across paragraphs and floats.

    A body paragraph that stops mid-sentence is joined with the next body paragraph.  If captions or
    complete paragraphs (table footnotes) intervene, the continuation is searched a few paragraphs ahead
    and must start with a lowercase letter; the intervening floats stay where they are, after the merge.
    """
    s = m.s
    spans: List[Tuple[int, int]] = []
    pos = 0
    for mo in re.finditer(r"\n{2,}", s):
        spans.append((pos, mo.start()))
        pos = mo.end()
    spans.append((pos, len(s)))
    texts = [s[a:b] for a, b in spans]

    def is_body(i: int) -> bool:
        t = texts[i]
        return bool(t.strip()) and not is_heading(t) and not is_caption(t) and not t.lstrip().startswith(("- ", "* ", "• "))

    used = [False] * len(spans)
    order: List[Mapped] = []
    for i in range(len(spans)):
        if used[i]:
            continue
        cur = slice_mapped(m, *spans[i])
        used[i] = True
        if is_body(i):
            j_from = i
            while _unfinished(cur.s):
                cand = None
                # adjacent paragraph first, then look ahead over floats
                for k in range(j_from + 1, min(len(spans), j_from + 6)):
                    if used[k]:
                        continue
                    if is_heading(texts[k]):
                        break
                    if is_body(k):
                        adjacent = all(used[x] for x in range(j_from + 1, k))
                        tail = cur.s.rstrip()[-1:]
                        midsentence = tail.isalnum() or tail in ",-(&"
                        if texts[k][:1].islower() or (adjacent and midsentence):
                            cand = k
                            break
                        continue  # a complete paragraph (e.g. table footnote): keep scanning
                    # caption or complete float paragraph: keep scanning
                if cand is None:
                    break
                nxt = slice_mapped(m, *spans[cand])
                cur = concat_mapped([cur, _sep(cur, " "), nxt])
                used[cand] = True
                j_from = cand
        order.append(cur)
    parts: List[Mapped] = []
    for k, p in enumerate(order):
        if k:
            parts.append(_sep(order[k - 1], "\n\n"))
        parts.append(p)
    return concat_mapped(parts) if parts else m


# ----------------------------------------------------------------------------- step D: hyphenation
def rejoin_hyphens(m: Mapped) -> Mapped:
    s = m.s
    vocab = Counter(w.lower() for w in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", s))
    edits: List[Edit] = []
    for mo in re.finditer(r"([A-Za-z]+)-([ \t]+|\n)(?=([a-z]+))", s):
        left, right = mo.group(1).lower(), mo.group(3).lower()
        if right in _STOP_RIGHT or len(left) < 2:
            continue
        joined, hyph = left + right, left + "-" + right
        if vocab.get(joined) or not vocab.get(hyph):
            edits.append((mo.start() + len(mo.group(1)), mo.end(), ""))       # delete "-" + whitespace
        else:
            edits.append((mo.start() + len(mo.group(1)) + 1, mo.end(), ""))   # real hyphen: delete whitespace only
    return m.edit(edits) if edits else m


# ----------------------------------------------------------------------------- driver
def _front_end_line(s: str) -> int:
    """Line index of the first recognised section heading (front matter ends there)."""
    for i, (a, b) in enumerate(_lines(s)):
        t = s[a:b]
        if t.strip() and (heading_code(t) not in (None, "noise")):
            return i
    return min(80, len(_lines(s)))


def clean(raw: str) -> CleanResult:
    res = CleanResult(Mapped.from_raw(raw))
    m = res.cleaned

    def step(name: str, fn: Callable[[Mapped], Mapped]) -> None:
        nonlocal m
        try:
            m = fn(m)
        except Exception as e:  # noqa: BLE001
            log.warning("clean step %s failed (%r); skipping it", name, e)
            res.fallbacks.append(f"clean:{name}")

    step("markup", strip_markup)
    step("ws1", normalise_whitespace)
    step("lines", lambda x: drop_lines(x, _front_end_line(x.s)))
    step("ws2", normalise_whitespace)
    step("merge", merge_paragraphs)
    step("hyphens", rejoin_hyphens)
    step("ws3", lambda x: x.edit([(mo.start(), mo.end(), " ") for mo in re.finditer(r"[ \t]{2,}", x.s)]))
    res.cleaned = m
    return res
