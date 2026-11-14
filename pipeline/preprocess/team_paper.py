#!/usr/bin/env python3
"""
preprocess_paper.py
===================

Clean ONE converted-PDF markdown article and split it into paragraphs ready for
CAMO causal-claim extraction (Evidence Jam 2026, Lane 1).

Design
------
* Every preprocessing step is its own function, registered in ``STEPS`` with a
  category:

    robustness       repairs conversion damage so the text reads correctly
                     (ligatures, hyphenation, page furniture, split sentences ...)
    token_reduction  removes text the extractor does not need
                     (references, tables, citations, introduction ...)
    structure        required plumbing (block split + section detection);
                     always runs and cannot be disabled.

  Any robustness / token_reduction step can be switched off by name or by
  category, so you can measure how many tokens each step saves and how the
  paragraphs degrade without it (see ``--ablation``).

* Offsets are never lost. Every character of the cleaned text carries the
  offset of the character it came from in the ORIGINAL file
  (``TrackedText.pos``). Paragraphs are exported with ``offset_runs`` so a quote
  found later can be mapped back to CAMO ``TextSpan.start_char / end_char``
  (see ``Paragraph.to_original`` and ``find_quote``).

* Paragraph selection (``select_paragraphs``) scores every 'extract' paragraph
  with a high-recall cue lexicon (causal verbs, null results, association,
  statistics, comparisons, hedges, mechanisms) and drops low-scoring ones.
  ``apply_token_budget`` optionally caps extract tokens per article.

* Chunk packing (``pack``) is a separate stage after preprocessing: it splits
  over-long paragraphs at sentence boundaries, packs paragraphs into balanced,
  labelled LLM chunks ("[P4|results] ...") and builds a compact study-card
  context from title / aims / methods sentences.

* Pure Python standard library. ``tiktoken`` or ``transformers`` are optional
  and only used for token counting. No network, no LLM calls.

Usage
-----
    python preprocess_paper.py corpus/YKQQZV93.md -o out.json
    python preprocess_paper.py paper.md --disable remove_inline_citations drop_back_matter
    python preprocess_paper.py paper.md --only robustness      # token steps off
    python preprocess_paper.py paper.md --ablation             # tokens saved per step
    python preprocess_paper.py paper.md --print                # show paragraphs
    python preprocess_paper.py --list-steps
    python preprocess_paper.py paper.md --pack --print-chunks   # LLM-ready chunks
    python preprocess_paper.py paper.md --scores               # selection scores
    python preprocess_paper.py paper.md --sweep 0 2 3 4 5      # tune --min-score
    python preprocess_paper.py paper.md --pack --min-score 4 --budget 3000 --max-chunk-tokens 2000

Python API
----------
    from preprocess_paper import preprocess, pack, Config, PackConfig
    res = preprocess(text, disabled={"route_sections"}, config=Config(min_score=3))
    for p in res.paragraphs:
        print(p.id, p.section, p.route, p.score, p.text[:80])
    packed = pack(res, PackConfig(max_chunk_tokens=2500))
    for c in packed.chunks:
        send_to_llm(packed.study_card.text, c.text)      # your extractor
    par = packed.units["P7.2"]                         # map a quoted id back
    span = find_quote(par, "were not affected by")      # -> original offsets
"""
from __future__ import annotations

import argparse
import math
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

ROBUSTNESS = "robustness"
TOKEN_REDUCTION = "token_reduction"
STRUCTURE = "structure"
CATEGORIES = (ROBUSTNESS, TOKEN_REDUCTION, STRUCTURE)


# =============================================================================
# 1. Offset-tracking text
# =============================================================================
class TrackedText:
    """A string in which every character remembers its offset in the original file.

    All edits go through ``sub``, ``keep_groups`` or ``delete_ranges``.
    Deleted characters disappear together with their offsets. Characters that are
    inserted by a replacement of different length are all mapped to the start
    offset of the text they replaced, so spans stay close to the source.
    """

    __slots__ = ("text", "pos")

    def __init__(self, text: str, pos: list[int] | None = None):
        self.text = text
        self.pos = pos if pos is not None else list(range(len(text)))

    def __len__(self) -> int:
        return len(self.text)

    def _anchor(self, i: int) -> int:
        if i < len(self.pos):
            return self.pos[i]
        return self.pos[-1] + 1 if self.pos else 0

    def sub(self, pattern: str | re.Pattern, repl: str | Callable[[re.Match], str] = "",
            flags: int = 0) -> int:
        """Regex substitution that keeps offsets. Returns the number of changes."""
        rx = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        out: list[str] = []
        pos: list[int] = []
        last = n = 0
        for m in rx.finditer(self.text):
            a, b = m.span()
            r = repl(m) if callable(repl) else m.expand(repl)
            if r == m.group(0):
                continue
            out.append(self.text[last:a])
            pos.extend(self.pos[last:a])
            if r:
                if len(r) == b - a:
                    pos.extend(self.pos[a:b])
                else:
                    pos.extend([self._anchor(a)] * len(r))
                out.append(r)
            last = b
            n += 1
        if n:
            out.append(self.text[last:])
            pos.extend(self.pos[last:])
            self.text, self.pos = "".join(out), pos
        return n

    def keep_groups(self, pattern: str | re.Pattern, flags: int = 0) -> int:
        """Replace each match by its capture groups (in order), keeping their exact
        offsets. Use for unwrapping markup, e.g. ``[text](#link)`` -> ``text``."""
        rx = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        out: list[str] = []
        pos: list[int] = []
        last = n = 0
        for m in rx.finditer(self.text):
            a, b = m.span()
            if a == b:
                continue
            out.append(self.text[last:a])
            pos.extend(self.pos[last:a])
            for g in range(1, rx.groups + 1):
                if m.group(g) is not None:
                    ga, gb = m.span(g)
                    out.append(self.text[ga:gb])
                    pos.extend(self.pos[ga:gb])
            last = b
            n += 1
        if n:
            out.append(self.text[last:])
            pos.extend(self.pos[last:])
            self.text, self.pos = "".join(out), pos
        return n

    def delete_ranges(self, ranges: Iterable[tuple[int, int]]) -> int:
        """Delete [start, end) ranges of the current text."""
        rs = sorted(r for r in ranges if r[1] > r[0])
        if not rs:
            return 0
        out: list[str] = []
        pos: list[int] = []
        last = n = 0
        for a, b in rs:
            a = max(a, last)
            if b <= a:
                continue
            out.append(self.text[last:a])
            pos.extend(self.pos[last:a])
            last = b
            n += 1
        out.append(self.text[last:])
        pos.extend(self.pos[last:])
        self.text, self.pos = "".join(out), pos
        return n

    def slice(self, a: int, b: int) -> "TrackedText":
        return TrackedText(self.text[a:b], self.pos[a:b])

    def lines(self) -> Iterator[tuple[int, int, str]]:
        """Yield (start, end_including_newline, line_without_newline)."""
        i = 0
        t = self.text
        while i < len(t):
            j = t.find("\n", i)
            if j == -1:
                yield i, len(t), t[i:]
                break
            yield i, j + 1, t[i:j]
            i = j + 1


def pos_to_runs(pos: list[int]) -> list[list[int]]:
    """Compress a position array into [clean_start, orig_start, length] runs."""
    runs: list[list[int]] = []
    if not pos:
        return runs
    cs, os_, ln = 0, pos[0], 1
    for i in range(1, len(pos)):
        if pos[i] == pos[i - 1] + 1:
            ln += 1
        else:
            runs.append([cs, os_, ln])
            cs, os_, ln = i, pos[i], 1
    runs.append([cs, os_, ln])
    return runs


def runs_lookup(runs: list[list[int]], i: int) -> int:
    """Original offset of cleaned character i, given offset runs."""
    lo, hi = 0, len(runs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        cs, os_, ln = runs[mid]
        if i < cs:
            hi = mid - 1
        elif i >= cs + ln:
            lo = mid + 1
        else:
            return os_ + (i - cs)
    raise IndexError(i)


# =============================================================================
# 2. Data structures
# =============================================================================
@dataclass
class Block:
    tt: TrackedText
    kind: str = "text"          # text | heading | caption
    section: str = "front"      # internal section name (see SECTION_RULES)
    heading: str = ""           # nearest heading text above this block
    route: str = "extract"      # extract | context | drop
    drop_reason: str | None = None
    score: float | None = None  # selection score (set by select_paragraphs)
    cues: dict = field(default_factory=dict)  # cue category -> hits

    @property
    def text(self) -> str:
        return self.tt.text

    def words(self) -> int:
        return len(self.tt.text.split())


@dataclass
class Config:
    """Settings for the selection steps (everything else is rule-based)."""
    min_score: float = 3.0                       # keep 'extract' paragraphs scoring >= this
    always_keep_sections: tuple[str, ...] = ("abstract",)
    keep_null_results: bool = True               # any null-result cue keeps a paragraph
    max_extract_tokens: int | None = None        # per-article budget for 'extract' tokens


@dataclass
class Doc:
    original: str
    tt: TrackedText
    blocks: list[Block] | None = None
    config: Config = field(default_factory=Config)
    count: Callable[[str], int] = lambda s: (len(s) + 3) // 4


@dataclass
class Paragraph:
    id: str
    section: str                 # internal section name
    camo_section: str | None     # value for CAMO DocumentSectionEnum (or None)
    route: str                   # extract -> LLM chunks; context -> study card
    heading: str
    text: str
    n_tokens: int
    orig_start: int
    orig_end: int
    offset_runs: list[list[int]]
    score: float | None = None
    cues: dict = field(default_factory=dict)
    parent: str | None = None    # set on pieces made by splitting a long paragraph

    def sentences(self) -> list[tuple[int, int]]:
        """Sentence spans [start, end) within ``self.text`` (for TextSpan.sentence_id)."""
        return sentence_spans(self.text)

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a [start, end) span of ``self.text`` to offsets in the original file."""
        if end <= start:
            raise ValueError("empty span")
        return runs_lookup(self.offset_runs, start), runs_lookup(self.offset_runs, end - 1) + 1

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class StepReport:
    name: str
    category: str
    level: str
    enabled: bool
    changes: int
    tokens_before: int
    tokens_after: int

    @property
    def saved(self) -> int:
        return self.tokens_before - self.tokens_after


@dataclass
class PreprocessResult:
    source: str
    tokens_original: int
    paragraphs: list[Paragraph]
    dropped: list[dict]
    steps: list[StepReport]
    disabled: list[str]
    health: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    heading_tokens: int = 0     # headings are not sent to the LLM (kept as Paragraph.heading)

    def tokens_by_route(self) -> dict[str, int]:
        c: Counter = Counter()
        for p in self.paragraphs:
            c[p.route] += p.n_tokens
        return dict(c)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "disabled_steps": self.disabled,
            "config": self.config,
            "tokens_original": self.tokens_original,
            "tokens_by_route": self.tokens_by_route(),
            "heading_tokens_not_sent": self.heading_tokens,
            "health": self.health,
            "steps": [s.__dict__ | {"saved": s.saved} for s in self.steps],
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "dropped": self.dropped,
        }


# =============================================================================
# 3. Token counting (only relative savings matter; plug in the model tokenizer
#    with --tokenizer hf:<name> if you have it locally)
# =============================================================================
def make_token_counter(spec: str = "auto") -> Callable[[str], int]:
    if spec.startswith("hf:"):
        from transformers import AutoTokenizer  # optional dependency
        tok = AutoTokenizer.from_pretrained(spec[3:])
        return lambda s: len(tok.encode(s, add_special_tokens=False))
    if spec in ("auto", "tiktoken"):
        try:
            import tiktoken  # optional dependency
            enc = tiktoken.get_encoding("cl100k_base")
            return lambda s: len(enc.encode(s, disallowed_special=()))
        except ImportError:
            if spec == "tiktoken":
                raise
    return lambda s: (len(s) + 3) // 4  # rough fallback: ~4 characters per token


# =============================================================================
# 4. Section vocabulary and heading detection
# =============================================================================
# Internal section names. "back:*" sections are front/back matter to drop.
SECTION_RULES: list[tuple[str, str]] = [
    ("back:references", r"(?:references?(?: cited)?|literature cited|bibliography|works cited|cited literature)"),
    ("back:acknowledgements", r"acknowledge?ments?"),
    ("back:funding", r"(?:funding(?: information| sources?)?|financial support|sources? of funding)"),
    ("back:contributions", r"(?:authors?'?’?s?'? contributions?|credit authorship|contributions)"),
    ("back:conflicts", r"(?:conflicts? of interests?|competing interests?|declaration of (?:competing interests?|interests?)|declarations?)"),
    ("back:data", r"(?:data (?:availability|accessibility|archiving)(?: statement)?|open research|data and code availability)"),
    ("back:other", r"(?:orcid|how to cite(?: this article)?|ethics(?: statement)?|biosketch|peer review)"),
    ("highlights", r"(?:highlights|key ?points|implications for practice)"),
    ("abstract", r"(?:abstract|summary|synopsis)"),
    ("introduction", r"(?:introduction|background)"),
    ("methods", r"(?:materials? and methods?|methods? and materials?|methods?|methodology|study (?:area|areas|site|sites|system|species|design)|site descriptions?|experimental (?:design|setup)|field methods|sampling(?: design| methods)?|data (?:analys[ie]s|collection)|statistical analys[ie]s|analys[ie]s)"),
    ("results", r"(?:results?(?: and discussion)?)"),
    ("discussion", r"(?:(?:general )?discussion)"),
    ("conclusion", r"(?:conclusions?|concluding remarks|management implications|implications(?: for (?:management|restoration|conservation))?|synthesis|recommendations)"),
    ("supplementary", r"(?:appendix|appendices|supplementa\w*|supporting information|electronic supplementary\w*)"),
]
_SECTION_RX = [(name, re.compile(rx + r"\b")) for name, rx in SECTION_RULES]

# Mapping to CAMO DocumentSectionEnum (title, abstract, introduction, methods,
# results, discussion, conclusion, supplementary). Others -> None.
CAMO_SECTION = {
    "title": "title", "abstract": "abstract", "highlights": "abstract",
    "introduction": "introduction", "methods": "methods", "results": "results",
    "discussion": "discussion", "conclusion": "conclusion", "supplementary": "supplementary",
}

# Where each section goes: extract -> LLM finding extraction,
# context -> study card only, drop -> not sent at all.
ROUTES = {
    "title": "context", "front": "extract", "abstract": "extract", "highlights": "extract",
    "introduction": "drop", "methods": "context", "results": "extract",
    "discussion": "extract", "conclusion": "extract", "supplementary": "context",
    "unknown": "extract",
}

_STANDARD_NAMES = {
    "abstract", "summary", "introduction", "background", "methods", "method",
    "materials and methods", "material and methods", "methodology", "study area",
    "study site", "study sites", "results", "result", "discussion", "results and discussion",
    "conclusion", "conclusions", "acknowledgements", "acknowledgments", "acknowledgement",
    "references", "literature cited", "bibliography", "highlights", "implications for practice",
    "appendix", "supporting information", "data availability statement",
}

_NUMBERING = re.compile(r"^(?:\d+(?:\.\d+)*|[ivxlc]+)[.)]?\s+", re.I)


def _clean_heading(title: str) -> str:
    s = title.strip()
    s = re.sub(r"^#+\s*", "", s)
    s = s.strip("*_ \t")
    s = _NUMBERING.sub("", s)
    s = s.strip("*_ \t").rstrip(":").strip()
    return s


def canonical_section(title: str) -> str | None:
    """Map a heading to an internal section name, or None for sub-headings."""
    s = _clean_heading(title).lower().replace("’", "'")
    if not s or len(s.split()) > 8:
        return None
    if s.endswith(".") and len(s.split()) > 2:
        return None
    s = s.rstrip(".")
    for name, rx in _SECTION_RX:
        if rx.match(s):
            return name
    return None


_NUM_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*|[IVX]+)[.)]?\s+[A-Z][^\n]{0,100}$")


def heading_strength(line: str) -> int:
    """2 = strong heading signal, 1 = weak (known section word only), 0 = not a heading."""
    s = line.strip()
    if not s or len(s) > 140:
        return 0
    if s.startswith("#"):
        return 2
    if re.fullmatch(r"\*\*[^*\n]{1,120}\*\*:?|__[^_\n]{1,120}__:?", s):
        return 2
    if _clean_heading(s).lower().rstrip(".") in _STANDARD_NAMES:
        return 2
    if (len(s.split()) <= 12 and not s.endswith((".", ",", ";"))
            and _NUM_HEADING.match(s)):
        return 2
    letters = [c for c in s if c.isalpha()]
    if (len(letters) >= 4 and len(s) <= 80 and not s.endswith(".")
            and sum(c.isupper() for c in letters) / len(letters) > 0.85):
        return 2
    if canonical_section(s) is not None and not s.endswith("."):
        return 1
    return 0


# =============================================================================
# 5. Step registry
# =============================================================================
@dataclass(frozen=True)
class Step:
    name: str
    category: str
    level: str          # text (whole document) | block (per paragraph block)
    func: Callable[[Doc], int]
    summary: str


STEPS: list[Step] = []  # pipeline order == definition order below


def step(category: str, level: str):
    def deco(f: Callable[[Doc], int]):
        summary = (f.__doc__ or "").strip().splitlines()[0] if f.__doc__ else ""
        STEPS.append(Step(f.__name__, category, level, f, summary))
        return f
    return deco


def _live(doc: Doc, include_headings: bool = False) -> Iterator[Block]:
    for b in doc.blocks or []:
        if b.route == "drop":
            continue
        if b.kind == "heading" and not include_headings:
            continue
        yield b


def _drop(b: Block, reason: str) -> None:
    b.route = "drop"
    b.drop_reason = reason


# =============================================================================
# 6. TEXT-LEVEL STEPS (whole document, before splitting)
# =============================================================================
_ZERO_WIDTH = set("\u200b\u200c\u200d\u2060\ufeff\u00ad")


@step(ROBUSTNESS, "text")
def normalize_unicode(doc: Doc) -> int:
    """NFKC-normalise characters (ligatures fi/fl, superscripts, nbsp) and drop zero-width/soft hyphens."""
    tt = doc.tt
    out: list[str] = []
    pos: list[int] = []
    changes = 0
    for ch, p in zip(tt.text, tt.pos):
        if ch in _ZERO_WIDTH:
            changes += 1
            continue
        n = unicodedata.normalize("NFKC", ch) if ord(ch) > 127 else ch
        if n != ch:
            changes += 1
        out.append(n)
        pos.extend([p] * len(n))
    tt.text, tt.pos = "".join(out), pos
    return changes


@step(ROBUSTNESS, "text")
def strip_html(doc: Doc) -> int:
    """Remove inline HTML/XML tags and comments (keeping their inner text) and decode entities."""
    n = doc.tt.sub(r"<!--.*?-->", "", re.S)
    n += doc.tt.sub(r"<br\s*/?>", " ", re.I)
    n += doc.tt.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>\n]{0,300})?/?>", "")
    n += doc.tt.sub(r"&(?:[A-Za-z]{2,8}|#\d{1,6}|#x[0-9A-Fa-f]{1,6});", lambda m: html.unescape(m.group(0)))
    return n


@step(TOKEN_REDUCTION, "text")
def remove_image_placeholders(doc: Doc) -> int:
    """Delete image placeholders such as ![](img.png), <!-- image -->, [image] and <img>."""
    n = doc.tt.sub(r"!\[[^\]\n]*\]\([^)\n]*\)", "")
    n += doc.tt.sub(r"<!--\s*image\s*-->", "", re.I)
    n += doc.tt.sub(r"<img\b[^>]*>", "", re.I)
    n += doc.tt.sub(r"\[(?:image|img|figure|picture)[^\]\n]{0,80}\]", "", re.I)
    return n


@step(ROBUSTNESS, "text")
def unwrap_markdown_links(doc: Doc) -> int:
    """Unwrap [text](#anchor) / [text](http..) links to plain text and unescape \\[ \\] \\* \\_."""
    n = doc.tt.keep_groups(r"(?<!!)\[([^\]\n]{1,300})\]\((?:#|https?://|www\.)[^)\n]*\)")
    n += doc.tt.sub(r"\\(?=[\[\]()*_#.\-+!|`])", "")
    return n


_PAGE_PATTERNS = [
    r"^[ \t]*\d{1,4}[ \t]*$\n?",                                   # bare page number
    r"^[ \t]*(?:page|p\.)[ \t]*\d+(?:[ \t]*(?:of|/)[ \t]*\d+)?[ \t]*$\n?",
    r"^[ \t]*[-–—_=*][-–—_=* \t]{2,}$\n?",                         # rules / separators
    r"^.*\b(?:Downloaded from|This article is protected by copyright|Terms and Conditions"
    r"|wileyonlinelibrary\.com|onlinelibrary\.wiley\.com|sciencedirect\.com|For personal use only"
    r"|Accepted Article|Author Manuscript|journal homepage)\b.*$\n?",
]


@step(ROBUSTNESS, "text")
def remove_page_artifacts(doc: Doc) -> int:
    """Delete page furniture lines: bare page numbers, separators, 'Downloaded from', publisher banners."""
    n = 0
    for p in _PAGE_PATTERNS:
        n += doc.tt.sub(p, "", re.M | re.I)
    return n


@step(ROBUSTNESS, "text")
def remove_running_headers(doc: Doc) -> int:
    """Delete short lines repeated 3+ times (running headers/footers inserted mid-paragraph)."""
    def key(line: str) -> str:
        return re.sub(r"\d+", "#", line.strip().lower())

    counts: Counter = Counter()
    for _, _, line in doc.tt.lines():
        s = line.strip()
        if 3 <= len(s) <= 120 and not s.startswith("|") and sum(c.isalpha() for c in s) >= 3:
            counts[key(line)] += 1
    repeated = {k for k, c in counts.items() if c >= 3}
    if not repeated:
        return 0
    ranges = [(a, b) for a, b, line in doc.tt.lines()
              if line.strip() and key(line) in repeated and heading_strength(line) < 2]
    return doc.tt.delete_ranges(ranges)


_META_LINE = re.compile(
    r"(?:\S+@\S+\.[a-z]{2,}"
    r"|^\W*(?:received|accepted|revised|published(?: online)?|available online|article history"
    r"|first published|handling editor|coordinating editor|correspondence|corresponding author"
    r"|e-?mail|address for correspondence|key ?words|index terms|citation|how to cite|cite this)\b"
    r"|©|\(c\)\s*(?:19|20)\d{2}|\bcopyright\b|all rights reserved"
    r"|^\W*(?:https?://)?(?:dx\.)?doi(?:\.org)?\s*[:/]|\borcid\b)",
    re.I,
)
_AFFILIATION = re.compile(
    r"^\W*(?:\d+|[a-z]|[*†‡§])?\W*(?:department|dept\.|university|institute|school|faculty|"
    r"cent(?:re|er)|laborator(?:y|ies)|college|division|ministry|agency|museum)\b", re.I)


@step(TOKEN_REDUCTION, "text")
def remove_metadata_lines(doc: Doc) -> int:
    """Delete metadata lines: emails, received/accepted dates, copyright, DOI, keywords, affiliations."""
    limit = int(len(doc.tt.text) * 0.25)  # affiliations only near the top
    ranges = []
    for a, b, line in doc.tt.lines():
        s = line.strip()
        if not s or len(s) > 300:
            continue
        if _META_LINE.search(s) or (a < limit and _AFFILIATION.match(s)):
            ranges.append((a, b))
    return doc.tt.delete_ranges(ranges)


# Words that legitimately follow a hyphen in compounds (keep the hyphen).
_COMPOUND_TAILS = (
    "term|scale|based|specific|level|wide|like|dependent|independent|free|induced|related|year|"
    "old|rich|poor|tolerant|resistant|dominated|mediated|driven|derived|grown|fed|planted|treated|"
    "invaded|native|time|way|cover|density|size|type|order|ground|season|site|plot|day|month|week"
)


@step(ROBUSTNESS, "text")
def fix_hyphenation(doc: Doc) -> int:
    """Rejoin words split across line or page breaks ('manage-\\nment' -> 'management')."""
    tail = rf"(?!(?:{_COMPOUND_TAILS})\b)"
    # compound words: keep the hyphen, remove the break
    n = doc.tt.sub(rf"(?<=[a-z]-)[ \t]*\n\s*(?=(?:{_COMPOUND_TAILS})\b)", "")
    # ordinary words: remove hyphen + break
    n += doc.tt.sub(rf"(?<=[a-z])-[ \t]*\n\s*(?=[a-z]){tail}", "")
    # 'manage- ment' on one line (converter artefact), not 'pre- and post-'
    n += doc.tt.sub(rf"(?<=[a-z]{{2}})- (?=[a-z]{{2,}})(?!(?:and|or|to|nor|vs|versus)\b){tail}", "")
    return n


@step(ROBUSTNESS, "text")
def rejoin_split_paragraphs(doc: Doc) -> int:
    """Rejoin sentences split across a blank line by page breaks or removed headers/figures."""
    def repl(m: re.Match) -> str:
        s, (a, b) = m.string, m.span()
        prev_line = s[s.rfind("\n", 0, a) + 1:a]
        nl = s.find("\n", b)
        next_line = s[b:nl if nl != -1 else len(s)]
        p, q = prev_line.rstrip(), next_line.strip()
        if not p or not q:
            return m.group(0)
        if heading_strength(p) or heading_strength(q):
            return m.group(0)
        if q[0] in "|#-*•>!" or p.lstrip()[:1] in "|#":
            return m.group(0)
        if re.match(r"^\W*(?:table|fig\.?|figure)\s*[a-z]?\d", q, re.I):
            return m.group(0)
        last = p[-1]
        if last in ".!?:":
            return m.group(0)
        if q[0].islower():
            return " "
        if len(p) >= 60 and (last.isalpha() or last in ",;("):
            return " "
        return m.group(0)

    return doc.tt.sub(r"\n(?:[ \t]*\n)+[ \t]*", repl)


@step(ROBUSTNESS, "text")
def normalize_whitespace(doc: Doc) -> int:
    """Collapse runs of spaces/tabs, strip line-edge spaces and limit blank lines to one."""
    n = doc.tt.sub(r"[ \t]{2,}", " ")
    n += doc.tt.sub(r"[ \t]+$", "", re.M)
    n += doc.tt.sub(r"^[ \t]+", "", re.M)
    n += doc.tt.sub(r"\n{3,}", "\n\n")
    return n


# =============================================================================
# 7. STRUCTURE: split into blocks and assign sections (always runs)
# =============================================================================
_INLINE_LABEL = re.compile(
    r"^\W{0,4}(abstract|summary|introduction|results|discussion|conclusions?)\W{0,4}[:.—–-]\s*\S",
    re.I)


@step(STRUCTURE, "block")
def split_blocks_and_sections(doc: Doc) -> int:
    """Split on blank lines, detect headings and assign every block a section."""
    tt = doc.tt
    raw: list[Block] = []
    for m in re.finditer(r"(?:[^\n]|\n(?![ \t]*\n))+", tt.text):
        a, b = m.span()
        # trim surrounding whitespace
        while a < b and tt.text[a].isspace():
            a += 1
        while b > a and tt.text[b - 1].isspace():
            b -= 1
        if a >= b:
            continue
        blk = tt.slice(a, b)
        first_nl = blk.text.find("\n")
        if first_nl == -1:
            kind = "heading" if heading_strength(blk.text) else "text"
            raw.append(Block(blk, kind=kind))
        elif heading_strength(blk.text[:first_nl]) >= 2:
            raw.append(Block(blk.slice(0, first_nl), kind="heading"))
            raw.append(Block(blk.slice(first_nl + 1, len(blk)), kind="text"))
        else:
            raw.append(Block(blk, kind="text"))

    current: str | None = None
    current_heading = ""
    title_set = False
    for blk in raw:
        if blk.kind == "heading":
            name = canonical_section(blk.text)
            if name:
                current = name
            elif current is None and not title_set:
                blk.section = "title"
                blk.kind = "text"          # keep the title as a context paragraph
                blk.tt.sub(r"^#+\s*", "")
                title_set = True
                current_heading = _clean_heading(blk.text)
                continue
            current_heading = _clean_heading(blk.text)
            blk.section = current or "front"
            blk.heading = current_heading
            continue
        m = _INLINE_LABEL.match(blk.text)
        if m and len(blk.text) > 150:
            name = canonical_section(m.group(1))
            if name:
                current = name
        blk.section = current or "front"
        blk.heading = current_heading

    # post-pass: title, abstract and unlabelled prose in the preamble
    texts = [b for b in raw if b.kind != "heading"]
    if not title_set and texts and texts[0].section == "front" and texts[0].words() <= 30:
        texts[0].section = "title"
    # Front matter = short blocks BEFORE the abstract. Anything after the abstract
    # that still has no section (no headings found) is body text: 'unknown'.
    has_abstract = any(b.section in ("abstract", "highlights") for b in raw)
    after_abstract = False
    for b in texts:
        if b.section in ("abstract", "highlights"):
            after_abstract = True
            continue
        if b.section != "front":
            continue
        w = b.words()
        if not has_abstract and w >= 60:
            b.section = "abstract"
            has_abstract = after_abstract = True
        elif w >= 60 or (after_abstract and w >= 8):
            b.section = "unknown"

    doc.blocks = raw
    return len(raw)


# =============================================================================
# 8. BLOCK-LEVEL STEPS
# =============================================================================
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$|^[^|\n]*\|[^|\n]*\|[^|\n]*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
_CAPTION = re.compile(r"^\W{0,3}(?:table|fig\.?|figure)\s*[a-z]?\d+", re.I)


def _numeric_junk(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 60:
        return False
    digits = sum(c.isdigit() for c in s)
    letters = sum(c.isalpha() for c in s)
    return digits / max(1, len(s.replace(" ", ""))) >= 0.3 and letters <= 12


@step(TOKEN_REDUCTION, "block")
def remove_tables(doc: Doc) -> int:
    """Delete markdown/broken table grids but keep the 'Table N.' / 'Figure N.' caption line."""
    n = 0
    for b in _live(doc):
        lines = list(b.tt.lines())
        table_lines = [(a, e) for a, e, ln in lines if _TABLE_ROW.match(ln) or _TABLE_SEP.match(ln)]
        junk = [(a, e) for a, e, ln in lines if _numeric_junk(ln)]
        to_delete = list(table_lines)
        if len(junk) >= 3 and len(junk) >= 0.4 * len(lines):
            to_delete += junk
        if not to_delete:
            continue
        b.tt.delete_ranges(to_delete)
        n += 1
        rest = b.tt.text.strip()
        if not rest:
            _drop(b, "table")
        elif _CAPTION.match(rest) and len(rest.split()) <= 80:
            b.kind = "caption"
    return n


@step(ROBUSTNESS, "block")
def drop_fragments(doc: Doc) -> int:
    """Drop leftover fragments: blocks with < 4 words or mostly non-letters (stray labels, axis ticks)."""
    n = 0
    for b in _live(doc):
        s = b.tt.text.strip()
        nonspace = len(s.replace(" ", "").replace("\n", ""))
        letters = sum(c.isalpha() for c in s)
        if len(s.split()) < 4 or (nonspace and letters / nonspace < 0.5):
            if b.kind == "caption" and len(s.split()) >= 3:
                continue
            _drop(b, "fragment")
            n += 1
    return n


_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
_REF_START = re.compile(
    r"^\s*(?:\[\d+\]|\d+\.)?\s*(?:"
    r"(?:van |von |de |du |le |da )?[A-Z][A-Za-z'’\-]+,?\s+(?:[A-Z]\.\s?-?){1,3}"   # Smith, J. A.
    r"|(?:van |von |de )?[A-Z][A-Za-z'’\-]+\s+[A-Z]{1,3}[,.]"                         # Smith JA,
    r")")
_REF_DETAIL = re.compile(r"\d+\s*[:(]\s*\d+|\bdoi\b|\bpp?\.\s*\d|\d+\s*[–-]\s*\d+|\bin press\b", re.I)


def looks_like_reference(line: str) -> bool:
    return bool(_REF_START.match(line) and _YEAR.search(line) and _REF_DETAIL.search(line))


@step(TOKEN_REDUCTION, "block")
def drop_back_matter(doc: Doc) -> int:
    """Drop references, acknowledgements, funding, contributions, conflicts, data availability (by heading or reference-list shape)."""
    n = 0
    blocks = doc.blocks or []
    for b in blocks:
        if b.route != "drop" and b.section.startswith("back:"):
            _drop(b, b.section)
            n += 1
    # reference lists with no recognised heading, in the second half of the paper
    start = len(blocks) // 2
    run: list[Block] = []

    def flush() -> int:
        k = 0
        if len(run) >= 4:
            for r in run:
                if r.route != "drop":
                    _drop(r, "reference_list_heuristic")
                    k += 1
        run.clear()
        return k

    for b in blocks[start:]:
        if b.route == "drop" or b.kind == "heading":
            continue
        lines = [ln for _, _, ln in b.tt.lines() if ln.strip()]
        ref_lines = sum(looks_like_reference(ln) for ln in lines)
        if len(lines) >= 4 and ref_lines >= 4 and ref_lines >= 0.3 * len(lines):
            _drop(b, "reference_list_heuristic")
            n += 1
            n += flush()
        elif lines and looks_like_reference(lines[0]) and len(lines) <= 4:
            run.append(b)
        else:
            n += flush()
    n += flush()
    return n


@step(TOKEN_REDUCTION, "block")
def drop_front_matter(doc: Doc) -> int:
    """Drop short preamble blocks before the first section (author lists, affiliations, journal info)."""
    n = 0
    for b in _live(doc):
        if b.section == "front":
            _drop(b, "front_matter")
            n += 1
    return n


_AIMS = re.compile(
    r"\b(?:we (?:hypothesi[sz]ed|predicted|tested|asked|aimed|examined|investigated|evaluated|assessed|compared|quantified)"
    r"|(?:the )?(?:aims?|objectives?|goals?|purpose) of (?:this|the present|our) (?:study|work|paper|research|experiment)"
    r"|(?:this|the present|our) (?:study|paper|work) (?:aims|aimed|examines|investigates|tests|evaluates|assesses))\b",
    re.I)


@step(TOKEN_REDUCTION, "block")
def route_sections(doc: Doc) -> int:
    """Route by section: Results/Discussion/Abstract -> extract, Methods -> context, Introduction -> drop (aims kept as context)."""
    n = 0
    for b in _live(doc):
        if b.section.startswith("back:"):
            continue  # handled by drop_back_matter
        route = ROUTES.get(b.section, "extract")
        if b.section == "introduction" and _AIMS.search(b.text):
            route = "context"
        if route == "drop":
            _drop(b, f"section:{b.section}")
            n += 1
        elif route != b.route:
            b.route = route
            n += 1
    return n


_CIT_PREFIX = r"(?:(?:e\.g\.|i\.e\.|see(?: also)?|cf\.|reviewed (?:in|by)|but see|as in|after|following)\s*,?\s*)?"
_NAME = r"(?:(?:van|von|de|du|le|la|da|del|di)\s+)?[A-Z][A-Za-z'’\-]+"
_AUTHORS = rf"{_NAME}(?:\s+et\s+al\.?|(?:\s*,\s*{_NAME})*\s*(?:,\s*)?(?:and|&)\s+{_NAME})?"
_YEARS = (r"(?:(?:19|20)\d{2}[a-z]?(?:\s*,\s*(?:19|20)\d{2}[a-z]?)*"
          r"|in press|unpublished data|unpubl\.? data|pers\.? comm\.?|submitted)")
_CIT_SEG = re.compile(rf"^{_CIT_PREFIX}{_AUTHORS},?\s+{_YEARS}$")
_STATS_IN_PAREN = re.compile(r"[=<>±≤≥]|\bP\s*[<=>]|%|\bn\s*=", re.I)


def _is_citation_paren(content: str) -> bool:
    if _STATS_IN_PAREN.search(content) or not _YEAR.search(content) and "press" not in content:
        return False
    segs = [s.strip() for s in re.split(r";|,(?=\s*(?:(?:van|von|de)\s+)?[A-Z][a-z])", content) if s.strip()]
    return bool(segs) and all(_CIT_SEG.match(s) for s in segs)


@step(TOKEN_REDUCTION, "block")
def remove_inline_citations(doc: Doc) -> int:
    """Delete parenthetical author-year citations '(Smith et al. 2004; Lee 2010)' and numeric '[12-15]'."""
    def paren(m: re.Match) -> str:
        return "" if _is_citation_paren(m.group(1)) else m.group(0)

    n = 0
    for b in _live(doc):
        n += b.tt.sub(r"[ \t]?\(([^()\n]{3,400})\)", paren)
        n += b.tt.sub(r"[ \t]?\[\d{1,3}(?:\s*[–,\-]\s*\d{1,3})*\]", "")
    return n


@step(TOKEN_REDUCTION, "block")
def remove_figure_table_refs(doc: Doc) -> int:
    """Delete pointers like '(Fig. 2a)', '(see Table 3)', '(Appendix S1)' unless they contain statistics."""
    rx = re.compile(r"[ \t]?\((?:see\s+)?(?:figs?\.|figures?|tables?|tab\.|appendix|appendices|app\.|"
                    r"supplementary|supporting|online resource|electronic supplementary)[^()\n]{0,60}\)", re.I)

    def repl(m: re.Match) -> str:
        return m.group(0) if _STATS_IN_PAREN.search(m.group(0)) else ""

    return sum(b.tt.sub(rx, repl) for b in _live(doc))


@step(TOKEN_REDUCTION, "block")
def remove_urls(doc: Doc) -> int:
    """Delete URLs and bare DOIs inside paragraphs."""
    rx = r"[ \t]?(?:https?://|www\.)\S+|[ \t]?\bdoi:\s*\S+"
    return sum(b.tt.sub(rx, "", re.I) for b in _live(doc))


@step(TOKEN_REDUCTION, "block")
def strip_markdown_formatting(doc: Doc) -> int:
    """Delete emphasis markers (*italic*, **bold**, _x_), list bullets and '>' quote markers."""
    n = 0
    for b in _live(doc):
        n += b.tt.sub(r"(?<![\w*])\*{1,3}(?=\S)|(?<=\S)\*{1,3}(?![\w*])", "")
        n += b.tt.sub(r"(?<![\w_])_{1,3}(?=\S)|(?<=\S)_{1,3}(?![\w_])", "")
        n += b.tt.sub(r"^[ \t]*(?:[-*+•]|>)[ \t]+", "", re.M)
    return n


@step(ROBUSTNESS, "block")
def normalize_block_whitespace(doc: Doc) -> int:
    """Turn soft line breaks inside a paragraph into spaces and tidy spaces before punctuation."""
    n = 0
    for b in _live(doc):
        n += b.tt.sub(r"[ \t]*\n[ \t]*", " ")
        n += b.tt.sub(r"[ \t]{2,}", " ")
        n += b.tt.sub(r"[ \t]+(?=[,.;:)])", "")
        n += b.tt.sub(r"(?<=\()[ \t]+", "")
        n += b.tt.sub(r"^\s+|\s+$", "")
    return n


def _shingles(text: str, k: int = 3) -> set[tuple[str, ...]]:
    w = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


@step(TOKEN_REDUCTION, "block")
def dedupe_paragraphs(doc: Doc) -> int:
    """Drop paragraphs whose 3-word shingles are >=85% contained in an earlier kept paragraph (e.g. highlights)."""
    seen: list[set] = []
    n = 0
    for b in _live(doc):
        if b.words() < 15:
            continue
        sh = _shingles(b.text)
        if not sh:
            continue
        if any(len(sh & prev) / len(sh) >= 0.85 for prev in seen):
            _drop(b, "duplicate")
            n += 1
        else:
            seen.append(sh)
    return n


# --- Paragraph selection -----------------------------------------------------
# Cue categories: (name, weight, pattern). A category contributes weight * min(hits, 2),
# so long paragraphs cannot win on one repeated word. Negative weights penalise
# methods-style prose that slipped into Results. High recall is the goal: only
# paragraphs with almost no sign of a finding should fall below the threshold.
_NEG = r"\b(?:no|not|neither|nor|without|lack(?:ed)?)\b"
CUES: list[tuple[str, float, re.Pattern]] = [(n, w, re.compile(rx, re.I)) for n, w, rx in [
    ("null_result", 3.0,
     _NEG + r"[^.;]{0,40}?\b(?:significant(?:ly)?|effects?|differences?|differ(?:ed)?|affect(?:ed)?|"
     r"changes?|changed|influence[ds]?|impacts?|relationships?|correlat\w*|associat\w*|trends?)\b"
     r"|\bunaffected\b|\bdid not (?:significantly )?(?:differ|affect|change|vary|increase|decrease|"
     r"respond|alter|reduce|influence|improve)\b|\bn\.s\.|\bsimilar (?:among|between|across|in)\b"
     r"|\bremained (?:unchanged|similar|constant|stable)\b|\bregardless of\b"),
    ("causal_verb", 2.0,
     r"\b(?:increas|decreas|reduc|enhanc|suppress|promot|inhibit|facilitat|improv|impair|alter|"
     r"limit|restrict|stimulat|depress|prevent|elevat|boost|diminish|declin|eliminat|exclud|kill|"
     r"damag|benefit|hinder|accelerat|delay|outcompet|displac|recover|establish|depriv|mitigat|"
     r"protect|deplet|exacerbat|amplif|attenuat|offset|counteract|reverse)\w*"
     r"|\b(?:affect|influenc|impact|driv|caus|determin|control|mediat|moderat|regulat|constrain|"
     r"shap|favou?r|lower|rais|shift)(?:e[ds]?|ing|s)?\b"
     r"|\bresult(?:ed|s|ing)? in\b|\bl(?:ed|ead(?:s|ing)?) to\b|\beffects? (?:of|on)\b"
     r"|\brespon(?:se|ses|ded|d|ds) (?:of|to)\b|\bdepend(?:s|ed|ent)? on\b|\bcontribut\w* to\b"
     r"|\bdue to\b|\bas a (?:result|consequence)\b"),
    ("finding_frame", 2.0,
     r"\b(?:our|these|the|this) (?:results?|data|findings?|study|experiment|analys[ie]s|patterns?)"
     r"\s+(?:\w+\s+)?(?:suggest|indicate|show|demonstrate|confirm|support|reveal|impl(?:y|ies)|provide)\w*"
     r"|\bwe (?:found|observed|detected|showed|demonstrated)\b"),
    ("agency", 2.0,
     r"\b(?:effective(?:ly|ness)?|ineffective|successful(?:ly)?|strateg(?:y|ies)|"
     r"(?:management|restoration|control|conservation) (?:tools?|options?|approach\w*|practices?|actions?|"
     r"interventions?|techniques?|methods?|outcomes?|success)|recommend\w*|managers? (?:should|could|can)|"
     r"helps?(?: to)?|helped|allow(?:s|ed)?|enabl\w*|permit\w*)\b"),
    ("association", 2.0,
     r"\b(?:associat|correlat|covari|co-occur)\w*|\brelat(?:ed|ionships?) (?:to|with|between)\b"
     r"|\blinked (?:to|with)\b|\bpredict(?:ed|ors?|s)\b|\bexplained\b[^.;]{0,30}\bvariation\b"),
    ("statistic", 2.0,
     r"\b[Pp]\s*[<=>≤≥]\s*0?\.\d|\b[FtZHUW]\s*(?:\(\s*\d|[\d,.]*\s*=\s*-?\d)|χ\s*2|chi-?squared?"
     r"|\bR\s*2\b|\b[rR]\s*=\s*-?0?\.\d|±|\b[nN]\s*=\s*\d|\bCI\b|\bdf\s*=|\bS[ED]\b|\bAIC\b"
     r"|\bcoefficients?\b|\bsignifican\w*|\b\d+(?:\.\d+)?\s*%"),
    ("comparison", 1.0,
     r"\b(?:higher|lower|greater|fewer|more|less|larger|smaller|faster|slower|taller|shorter|"
     r"denser|richer)\b[^.;]{0,60}?\bthan\b|\bcompared (?:with|to)\b|\brelative to\b|\bversus\b"
     r"|\bvs\.?(?=\s)|\b(?:untreated|unburn(?:ed|t)|unmanaged|ungrazed|unplanted|uninvaded)\b"
     r"|\bcontrol (?:plots?|sites?|treatments?)\b|\breference (?:sites?|plots?|ecosystems?)\b"),
    ("hedge", 1.0,
     r"\b(?:may|might|could|suggest\w*|likely|unlikely|possibl[ey]|probabl[ey]|appear\w*|"
     r"indicat\w*|presumabl[ey]|potential(?:ly)?|impl(?:y|ies|ied))\b"),
    ("mechanism", 1.0,
     r"\b(?:through|via|because|mechanisms?|pathways?|thereby|owing to)\b"
     r"|\bby (?:increas|reduc|alter|limit|shad|compet)\w*"),
    ("methods_like", -1.0,
     r"\b(?:were|was) (?:sampled|collected|measured|recorded|estimated|calculated|analy[sz]ed|"
     r"counted|surveyed|harvested|weighed|placed|established|located|identified|transformed|"
     r"fitted|tested|log-transformed)\b|\busing (?:a|an|the)\b|\bpackage\b|\bsoftware\b"),
]]


def score_paragraph(text: str) -> tuple[float, dict[str, int]]:
    """Return (score, {cue category: hits}) for one paragraph."""
    cues: dict[str, int] = {}
    score = 0.0
    for name, weight, rx in CUES:
        hits = len(rx.findall(text))
        if hits:
            cues[name] = hits
            score += weight * min(hits, 2)
    return score, cues


def keep_paragraph(block: Block, cfg: Config) -> bool:
    """Selection rule (C8). Keep if the section is protected, the paragraph reports a
    null result (CAMO requires null results), or its cue score reaches the threshold."""
    if block.section in cfg.always_keep_sections:
        return True
    if cfg.keep_null_results and block.cues.get("null_result"):
        return True
    return (block.score or 0.0) >= cfg.min_score


@step(TOKEN_REDUCTION, "block")
def select_paragraphs(doc: Doc) -> int:
    """Score 'extract' paragraphs with the causal-cue lexicon and drop those below Config.min_score."""
    n = 0
    for b in list(_live(doc)):
        b.score, b.cues = score_paragraph(b.text)
        if b.route == "extract" and not keep_paragraph(b, doc.config):
            # Unlabelled sections (no headings found): methods-like prose still feeds the study card.
            if b.section in ("unknown", "front") and len(_DESIGN_CUE.findall(b.text)) >= 2:
                b.route = "context"
            else:
                _drop(b, "low_score")
            n += 1
    return n


_BUDGET_SECTION_BONUS = {"results": 1.0, "conclusion": 0.5, "abstract": 0.5, "discussion": 0.0}


@step(TOKEN_REDUCTION, "block")
def apply_token_budget(doc: Doc) -> int:
    """If Config.max_extract_tokens is set, drop the lowest-scoring 'extract' paragraphs until under budget."""
    cfg = doc.config
    if not cfg.max_extract_tokens:
        return 0
    ext = [(i, b) for i, b in enumerate(doc.blocks or []) if b.route == "extract" and b.kind != "heading"]
    total = sum(doc.count(b.text) for _, b in ext)
    if total <= cfg.max_extract_tokens:
        return 0

    def protected(b: Block) -> bool:
        return b.section in cfg.always_keep_sections or bool(cfg.keep_null_results and b.cues.get("null_result"))

    order = sorted((x for x in ext if not protected(x[1])),
                   key=lambda x: ((x[1].score or 0.0) + _BUDGET_SECTION_BONUS.get(x[1].section, 0.0), -x[0]))
    n = 0
    for _, b in order:
        if total <= cfg.max_extract_tokens:
            break
        total -= doc.count(b.text)
        _drop(b, "budget")
        n += 1
    return n


# =============================================================================
# 9. Pipeline runner
# =============================================================================
OPTIONAL_STEPS = [s.name for s in STEPS if s.category != STRUCTURE]

_STAT = re.compile(r"\b[Pp]\s*[<=>≤]\s*0?\.\d|\b[FtZ]\s*\(?\d|χ2|\bR2\b|±|\bn\s*=\s*\d|\b95\s*%\s*CI|\bdf\s*=")
_BINOMIAL = re.compile(r"\b[A-Z]\.\s[a-z]{3,}\b|\b[A-Z][a-z]+\s(?:[a-z]+(?:us|um|a|is|es|ii|ae|ata|ensis|oides|"
                       r"ana|ica|folia|ium|ens|ans|or|ix|ella|ata|osa|ia))\b")


def resolve_disabled(disable: Iterable[str] = (), only: Iterable[str] = ()) -> set[str]:
    """Names of steps to switch off. ``only`` keeps just the given categories
    (plus structure); ``disable`` accepts step names or category names."""
    disabled: set[str] = set()
    only = set(only)
    if only:
        bad = only - set(CATEGORIES)
        if bad:
            raise ValueError(f"unknown category in --only: {sorted(bad)}")
        disabled |= {s.name for s in STEPS if s.category != STRUCTURE and s.category not in only}
    for d in disable:
        if d in CATEGORIES:
            disabled |= {s.name for s in STEPS if s.category == d and s.category != STRUCTURE}
        elif d in OPTIONAL_STEPS:
            disabled.add(d)
        else:
            raise ValueError(f"unknown or non-optional step: {d!r}. Use --list-steps.")
    return disabled


def _doc_tokens(doc: Doc, count: Callable[[str], int]) -> int:
    """Tokens still in play. Headings are counted here (they are only removed at
    assembly), so the structure step does not appear to 'save' tokens."""
    if doc.blocks is None:
        return count(doc.tt.text)
    return sum(count(b.text) for b in _live(doc, include_headings=True))


def preprocess(text: str, disabled: Iterable[str] = (), tokenizer: str | Callable[[str], int] = "auto",
               source: str = "", config: Config | None = None) -> PreprocessResult:
    """Run the pipeline on one article. ``disabled`` = step names to skip."""
    count = tokenizer if callable(tokenizer) else make_token_counter(tokenizer)
    disabled = set(disabled)
    config = config or Config()
    doc = Doc(original=text, tt=TrackedText(text), config=config, count=count)
    tokens_original = count(text)
    reports: list[StepReport] = []
    current = tokens_original
    for s in STEPS:
        enabled = s.category == STRUCTURE or s.name not in disabled
        changes = s.func(doc) if enabled else 0
        after = _doc_tokens(doc, count) if enabled else current
        reports.append(StepReport(s.name, s.category, s.level, enabled, changes, current, after))
        current = after

    paragraphs: list[Paragraph] = []
    dropped: list[dict] = []
    for b in doc.blocks or []:
        t = b.text.strip()
        if not t or b.kind == "heading":
            continue
        if b.route == "drop":
            dropped.append({
                "reason": b.drop_reason, "section": b.section, "n_tokens": count(t),
                "orig_start": b.tt.pos[0], "orig_end": b.tt.pos[-1] + 1,
                "has_statistic": bool(_STAT.search(t)), "has_binomial": bool(_BINOMIAL.search(t)),
                "score": b.score, "cues": b.cues, "preview": t[:200],
            })
            continue
        lead = len(b.text) - len(b.text.lstrip())
        pos = b.tt.pos[lead:lead + len(t)]
        paragraphs.append(Paragraph(
            id=f"P{len(paragraphs) + 1}", section=b.section, camo_section=CAMO_SECTION.get(b.section),
            route=b.route, heading=b.heading, text=t, n_tokens=count(t),
            orig_start=pos[0], orig_end=pos[-1] + 1, offset_runs=pos_to_runs(pos),
            score=b.score, cues=b.cues,
        ))
    res = PreprocessResult(source, tokens_original, paragraphs, dropped, reports, sorted(disabled),
                           config=config.__dict__ | {"always_keep_sections": list(config.always_keep_sections)})
    res.heading_tokens = sum(count(b.text) for b in _live(doc, include_headings=True) if b.kind == "heading")
    res.health = health_metrics(res)
    return res


def preprocess_file(path: str | Path, **kw) -> PreprocessResult:
    p = Path(path)
    return preprocess(p.read_text(encoding="utf-8"), source=str(p), **kw)


# =============================================================================
# 10. Helpers for later stages
# =============================================================================
def find_quote(par: Paragraph, quote: str) -> tuple[int, int] | None:
    """Locate a (model-produced) quote in a paragraph and return ORIGINAL-file
    offsets (start, end), tolerant to case, whitespace and punctuation differences."""
    q = " ".join(quote.split())
    if not q:
        return None
    i = par.text.find(q)
    if i == -1:
        i = par.text.lower().find(q.lower())
    if i != -1:
        return par.to_original(i, i + len(q))
    words = re.findall(r"\w+", q)
    if len(words) < 3:
        return None
    rx = re.compile(r"\W+".join(map(re.escape, words)), re.I)
    m = rx.search(par.text)
    return par.to_original(*m.span()) if m else None


def health_metrics(res: PreprocessResult) -> dict:
    """Cheap robustness indicators: lower is better for every *_share / *_left value."""
    pars = res.paragraphs
    n = len(pars) or 1
    return {
        "n_paragraphs": len(pars),
        "sections": dict(Counter(p.section for p in pars)),
        "starts_lowercase_share": round(sum(p.text[:1].islower() for p in pars) / n, 3),
        "no_terminal_punct_share": round(
            sum(not re.search(r"[.!?:)\]\"'’”]\s*$", p.text) for p in pars) / n, 3),
        "short_paragraph_share": round(sum(len(p.text.split()) < 8 for p in pars) / n, 3),
        "html_tags_left": sum(len(re.findall(r"</?[A-Za-z][^>\n]{0,80}>", p.text)) for p in pars),
        "split_words_left": sum(len(re.findall(r"[a-z]- [a-z]{2,}", p.text)) for p in pars),
        "mean_tokens_per_paragraph": round(sum(p.n_tokens for p in pars) / n, 1),
        "dropped_with_statistic": sum(d["has_statistic"] for d in res.dropped),
        "dropped_with_binomial": sum(d["has_binomial"] for d in res.dropped),
        "selection_dropped": sum(d["reason"] in ("low_score", "budget") for d in res.dropped),
        "selection_dropped_with_statistic": sum(
            d["has_statistic"] for d in res.dropped if d["reason"] in ("low_score", "budget")),
    }


# =============================================================================
# 11. Sentence splitting
# =============================================================================
# Do not split after abbreviations common in ecology papers or after initials
# ("S. canadensis" is already safe: the next word is lowercase).
_NO_SPLIT_BEFORE = re.compile(
    r"(?:\b(?:et al|e\.g|i\.e|cf|[Ff]igs?|[Tt]abs?|[Ee]qs?|spp?|var|subsp|ssp|approx|ca|vs|[Nn]os?|"
    r"Dr|St|Mt|Ref|resp|sect|[Aa]pp|[Ss]uppl|[Vv]ol|pp?|ed|eds|[Jj]an|[Ff]eb|[Mm]ar|[Aa]pr|[Jj]un|[Jj]ul|"
    r"[Aa]ug|[Ss]ept?|[Oo]ct|[Nn]ov|[Dd]ec)\.|\b[A-Z]\.)$")
_SENT_END = re.compile(r"[.!?]([\"'’”)\]]*)\s+(?=[\"'‘“(\[]?[A-Z0-9])")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Split text into sentence spans [start, end), robust to 'et al.', 'Fig.', initials."""
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENT_END.finditer(text):
        if _NO_SPLIT_BEFORE.search(text[max(0, m.start() - 12):m.start() + 1]):
            continue
        end = m.end(1)
        if end > start:
            spans.append((start, end))
        start = m.end()
    if start < len(text) and text[start:].strip():
        spans.append((start, len(text.rstrip())))
    return spans


def runs_to_pos(runs: list[list[int]]) -> list[int]:
    """Expand [clean_start, orig_start, length] runs back to a position array."""
    pos: list[int] = []
    for _, os_, ln in runs:
        pos.extend(range(os_, os_ + ln))
    return pos


def split_paragraph(par: Paragraph, max_tokens: int, count: Callable[[str], int]) -> list[Paragraph]:
    """Split a paragraph longer than ``max_tokens`` at sentence boundaries into pieces
    P7.1, P7.2 ... Each piece keeps exact offsets into the original file. A single
    sentence longer than the limit stays whole (never cut mid-sentence)."""
    if par.n_tokens <= max_tokens:
        return [par]
    spans = sentence_spans(par.text)
    if len(spans) <= 1:
        return [par]
    groups: list[tuple[int, int]] = []
    g_start, g_end, g_tok = spans[0][0], spans[0][1], count(par.text[spans[0][0]:spans[0][1]])
    for a, b in spans[1:]:
        t = count(par.text[a:b])
        if g_tok + t > max_tokens:
            groups.append((g_start, g_end))
            g_start, g_end, g_tok = a, b, t
        else:
            g_end, g_tok = b, g_tok + t
    groups.append((g_start, g_end))
    if len(groups) == 1:
        return [par]
    pos = runs_to_pos(par.offset_runs)
    pieces = []
    for k, (a, b) in enumerate(groups, 1):
        text = par.text[a:b].strip()
        lead = len(par.text[a:b]) - len(par.text[a:b].lstrip())
        ppos = pos[a + lead:a + lead + len(text)]
        pieces.append(Paragraph(
            id=f"{par.id}.{k}", section=par.section, camo_section=par.camo_section, route=par.route,
            heading=par.heading, text=text, n_tokens=count(text), orig_start=ppos[0],
            orig_end=ppos[-1] + 1, offset_runs=pos_to_runs(ppos), score=par.score, cues=par.cues,
            parent=par.id))
    return pieces


# =============================================================================
# 12. Chunk packing
# =============================================================================
@dataclass
class PackConfig:
    max_chunk_tokens: int = 2500          # hard cap on paragraph text per LLM call
    max_paragraph_tokens: int | None = None  # split longer paragraphs (default: max_chunk_tokens // 2)
    label: str = "id_section"             # id_section -> "[P4|results] ", id -> "[P4] ", none
    split_long_paragraphs: bool = True
    prompt_overhead_tokens: int = 1500    # system prompt + few-shot resent with each chunk (estimate)
    study_card_tokens: int = 900          # budget for the study-card context
    study_card_overhead_tokens: int = 400  # prompt for the study-card call (estimate)
    include_study_card_in_chunks: bool = False  # prepend the card to every chunk instead of a separate call


@dataclass
class Chunk:
    id: str
    paragraph_ids: list[str]
    sections: list[str]
    text: str
    n_tokens: int
    est_input_tokens: int     # n_tokens + prompt overhead

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class PackResult:
    chunks: list[Chunk]
    study_card: Chunk | None
    units: dict[str, Paragraph]   # every id that can appear in a chunk (incl. split pieces and parents)
    config: dict

    @property
    def est_llm_input_tokens(self) -> int:
        n = sum(c.est_input_tokens for c in self.chunks)
        if self.study_card and not self.config.get("include_study_card_in_chunks"):
            n += self.study_card.est_input_tokens
        return n

    def summary(self) -> dict:
        return {
            "n_chunks": len(self.chunks),
            "chunk_tokens": [c.n_tokens for c in self.chunks],
            "study_card_tokens": self.study_card.n_tokens if self.study_card else 0,
            "est_llm_input_tokens": self.est_llm_input_tokens,
        }

    def to_dict(self) -> dict:
        return {"summary": self.summary(), "config": self.config,
                "study_card": self.study_card.to_dict() if self.study_card else None,
                "chunks": [c.to_dict() for c in self.chunks]}


def _label(p: Paragraph, style: str) -> str:
    if style == "none":
        return ""
    if style == "id":
        return f"[{p.id}] "
    sec = p.camo_section or ("body" if p.section in ("unknown", "front") else p.section)
    return f"[{p.id}|{sec}] "


def pack_chunks(pars: list[Paragraph], cfg: PackConfig, count: Callable[[str], int]) -> list[Chunk]:
    """Pack paragraphs (document order) into balanced chunks of <= max_chunk_tokens.

    Balanced packing: uses the minimum number of chunks that fits the cap, then the
    smallest per-chunk capacity that keeps that number, so chunks are evenly sized
    and there is never one full chunk plus a tiny tail (every chunk pays the full
    prompt overhead, and evenly sized chunks keep findings away from the middle of
    very long contexts)."""
    units = [(p, _label(p, cfg.label) + p.text) for p in pars]
    if not units:
        return []
    sizes = [count(t) + 1 for _, t in units]          # +1 for the separating newline

    def greedy(cap: int) -> list[list[int]]:
        groups: list[list[int]] = [[]]
        cur = 0
        for i, sz in enumerate(sizes):
            if groups[-1] and cur + sz > cap:
                groups.append([])
                cur = 0
            groups[-1].append(i)
            cur += sz
        return groups

    # 1) fewest chunks possible under the cap (greedy is optimal for contiguous packing);
    # 2) smallest capacity that still gives that many chunks -> evenly sized chunks.
    cap = max(cfg.max_chunk_tokens, max(sizes))      # a single unsplittable unit may exceed the cap
    k_min = len(greedy(cap))
    lo, hi = max(max(sizes), math.ceil(sum(sizes) / k_min)), cap
    while lo < hi:
        mid = (lo + hi) // 2
        if len(greedy(mid)) <= k_min:
            hi = mid
        else:
            lo = mid + 1
    groups = greedy(lo)
    chunks = []
    for k, g in enumerate(groups, 1):
        text = "\n\n".join(units[i][1] for i in g)
        secs: list[str] = []
        for i in g:
            sec = units[i][0].camo_section or units[i][0].section
            if sec not in secs:
                secs.append(sec)
        n = count(text)
        chunks.append(Chunk(f"C{k}", [units[i][0].id for i in g], secs, text, n,
                            n + cfg.prompt_overhead_tokens))
    return chunks


_DESIGN_CUE = re.compile(
    r"\b(?:study (?:area|site|sites|region)|located|plots?|quadrats?|transects?|blocks?|replicat\w*|"
    r"randomi[sz]ed|design|treatments?|controls?|experiment\w*|sampled|surveyed|monitored|"
    r"(?:19|20)\d{2}|°|elevation|altitude|climate|precipitation|temperature|soils?|forests?|"
    r"grasslands?|wetlands?|prairies?|savannas?|woodlots?|peatlands?|marsh\w*|meadows?|"
    r"restor\w*|planted|seeded|burn\w*|mow\w*|graz\w*|remov\w*|hectares?|ha\b|km\b|m2\b|"
    r"[nN]\s*=\s*\d|province|state|county|national park|reserve)\b", re.I)
_AIMS_SENT = re.compile(
    r"\b(?:we (?:hypothesi[sz]ed|predicted|tested|asked|aimed|examined|investigated|evaluated|assessed|"
    r"compared|quantified)|aims?|objectives?|goals?|purpose|questions?)\b", re.I)


def build_study_card(pars: list[Paragraph], cfg: PackConfig, count: Callable[[str], int]) -> Chunk | None:
    """Compact context for the study-card call: the title, then the best sentences from
    'context' paragraphs (aims, study area, design, sampling) within study_card_tokens.
    Sentences are ranked by design cues and printed back in document order."""
    ctx = [p for p in pars if p.route == "context"]
    if not ctx:
        return None
    budget = cfg.study_card_tokens
    picked: dict[str, list[tuple[int, int]]] = {}
    used = 0
    title = next((p for p in ctx if p.section == "title"), None)
    if title:
        picked[title.id] = [(0, len(title.text))]
        used += count(title.text)
    cands = []
    for order, p in enumerate(ctx):
        if p is title:
            continue
        rx = _AIMS_SENT if p.section == "introduction" else _DESIGN_CUE
        bonus = 2 if p.section == "introduction" else 0
        for a, b in p.sentences():
            sent = p.text[a:b]
            hits = len(rx.findall(sent))
            if hits:
                cands.append((-(min(hits, 6) + bonus), order, a, p, sent, b))
    for _, _, a, p, sent, b in sorted(cands, key=lambda x: (x[0], x[1], x[2])):
        t = count(sent) + 1
        if used + t > budget:
            continue
        picked.setdefault(p.id, []).append((a, b))
        used += t
    lines, ids, secs = [], [], []
    for p in ctx:
        if p.id not in picked:
            continue
        spans = sorted(picked[p.id])
        lines.append(_label(p, cfg.label) + " ".join(p.text[a:b] for a, b in spans))
        ids.append(p.id)
        sec = p.camo_section or p.section
        if sec not in secs:
            secs.append(sec)
    text = "\n\n".join(lines)
    n = count(text)
    return Chunk("CARD", ids, secs, text, n, n + cfg.study_card_overhead_tokens)


def pack(res: PreprocessResult, cfg: PackConfig | None = None,
         tokenizer: str | Callable[[str], int] = "auto") -> PackResult:
    """Turn a PreprocessResult into LLM-ready chunks plus a study-card context."""
    cfg = cfg or PackConfig()
    count = tokenizer if callable(tokenizer) else make_token_counter(tokenizer)
    units: dict[str, Paragraph] = {}
    extract: list[Paragraph] = []
    for p in res.paragraphs:
        units[p.id] = p
        if p.route != "extract":
            continue
        limit = cfg.max_paragraph_tokens or cfg.max_chunk_tokens // 2
        pieces = split_paragraph(p, limit, count) if cfg.split_long_paragraphs else [p]
        for q in pieces:
            units[q.id] = q
        extract.extend(pieces)
    card = build_study_card(res.paragraphs, cfg, count)
    chunks = pack_chunks(extract, cfg, count)
    if card and cfg.include_study_card_in_chunks:
        for c in chunks:
            c.text = f"STUDY CONTEXT\n{card.text}\n\nPARAGRAPHS\n{c.text}"
            c.n_tokens = count(c.text)
            c.est_input_tokens = c.n_tokens + cfg.prompt_overhead_tokens
    return PackResult(chunks, card, units, cfg.__dict__.copy())


# =============================================================================
# 13. CLI
# =============================================================================
def _print_steps() -> None:
    print(f"{'#':>2}  {'step':<28}{'category':<17}{'level':<7}description")
    for i, s in enumerate(STEPS, 1):
        print(f"{i:>2}  {s.name:<28}{s.category:<17}{s.level:<7}{s.summary}")


def _print_report(res: PreprocessResult) -> None:
    print(f"\n{res.source or '<text>'}  original tokens: {res.tokens_original}")
    print(f"{'step':<28}{'category':<17}{'on':<4}{'changes':>8}{'tokens':>9}{'saved':>8}")
    for s in res.steps:
        print(f"{s.name:<28}{s.category:<17}{'y' if s.enabled else '-':<4}{s.changes:>8}"
              f"{s.tokens_after:>9}{s.saved:>8}")
    r = res.tokens_by_route()
    kept = sum(r.values())
    pct = 100 * (1 - kept / res.tokens_original) if res.tokens_original else 0
    print(f"\nkept tokens: {kept}  (extract {r.get('extract', 0)}, context {r.get('context', 0)};"
          f" headings not sent: {res.heading_tokens})  saved {pct:.1f}% of original")
    print("health:", json.dumps(res.health))


def _print_pack(pk: PackResult, show_text: bool) -> None:
    sm = pk.summary()
    print(f"\nchunks: {sm['n_chunks']}  sizes {sm['chunk_tokens']}  study card {sm['study_card_tokens']} tok"
          f"  -> est. LLM input tokens {sm['est_llm_input_tokens']}"
          f" (incl. {pk.config['prompt_overhead_tokens']}/chunk prompt overhead)")
    items = ([pk.study_card] if pk.study_card else []) + pk.chunks
    for c in items:
        print(f"  {c.id:<5} {c.n_tokens:>5} tok  {','.join(c.sections):<32} {' '.join(c.paragraph_ids)}")
        if show_text:
            print("  " + "-" * 76)
            print("\n".join("  " + ln for ln in c.text.splitlines()))
            print("  " + "-" * 76)


def _print_scores(res: PreprocessResult) -> None:
    rows = [(p.orig_start, "keep", p.route, p.section, p.score, p.cues, p.text) for p in res.paragraphs
            if p.score is not None]
    rows += [(d["orig_start"], d["reason"], "drop", d["section"], d["score"], d["cues"], d["preview"])
             for d in res.dropped if d.get("score") is not None]
    print(f"\n{'status':<10}{'route':<8}{'section':<13}{'score':>6}  cues  |  text")
    for _, st, route, sec, sc, cues, text in sorted(rows, key=lambda r: r[0]):
        c = " ".join(f"{k[:4]}{v}" for k, v in cues.items())
        print(f"{st:<10}{route:<8}{sec:<13}{sc:>6.1f}  {c:<34}|  {text[:70]}")


def _ablation(text: str, source: str, tokenizer: str, cfg: Config, pcfg: PackConfig) -> None:
    count = make_token_counter(tokenizer)
    rob = [s.name for s in STEPS if s.category == ROBUSTNESS]
    tok = [s.name for s in STEPS if s.category == TOKEN_REDUCTION]
    configs: list[tuple[str, set[str]]] = [
        ("structure only (raw)", set(OPTIONAL_STEPS)),
        ("robustness only", set(tok)),
        ("token_reduction only", set(rob)),
        ("all steps", set()),
    ] + [(f"all minus {n}", {n}) for n in OPTIONAL_STEPS]
    full = None
    rows = []
    for label, dis in configs:
        res = preprocess(text, disabled=dis, tokenizer=count, source=source, config=cfg)
        pk = pack(res, pcfg, count)
        ext = res.tokens_by_route().get("extract", 0)
        if label == "all steps":
            full = (ext, pk.est_llm_input_tokens)
        rows.append((label, res, ext, pk))
    print(f"\n{source}  original tokens: {rows[0][1].tokens_original}")
    print(f"{'configuration':<38}{'paras':>6}{'extract':>9}{'Δextract':>10}{'chunks':>7}{'LLM in':>8}"
          f"{'ΔLLM in':>9}{'lower%':>8}{'noPunct%':>9}{'split':>6}{'html':>6}")
    for label, res, ext, pk in rows:
        same = full is None or label == "all steps"
        d1 = "" if same else f"{ext - full[0]:+d}"
        d2 = "" if same else f"{pk.est_llm_input_tokens - full[1]:+d}"
        h = res.health
        print(f"{label:<38}{h['n_paragraphs']:>6}{ext:>9}{d1:>10}{len(pk.chunks):>7}"
              f"{pk.est_llm_input_tokens:>8}{d2:>9}"
              f"{100 * h['starts_lowercase_share']:>8.1f}{100 * h['no_terminal_punct_share']:>9.1f}"
              f"{h['split_words_left']:>6}{h['html_tags_left']:>6}")
    print("\nΔ columns on 'all minus X' rows = extra tokens when step X is off (= what step X saves).\n"
          "'LLM in' = estimated input tokens for the whole article incl. per-chunk prompt overhead.\n"
          "lower% / noPunct% / split / html are robustness indicators: they rise when a robustness step is off.")


def _sweep(text: str, source: str, tokenizer: str, cfg: Config, pcfg: PackConfig,
           thresholds: list[float]) -> None:
    count = make_token_counter(tokenizer)
    print(f"\n{source}: selection threshold sweep")
    print(f"{'min_score':>9}{'kept':>6}{'dropped':>8}{'extract':>9}{'chunks':>7}{'LLM in':>8}"
          f"{'drop w/ stat':>13}  dropped previews")
    for th in thresholds:
        c = Config(**{**cfg.__dict__, "min_score": th})
        res = preprocess(text, tokenizer=count, source=source, config=c)
        pk = pack(res, pcfg, count)
        sel = [d for d in res.dropped if d["reason"] in ("low_score", "budget")]
        ext = res.tokens_by_route().get("extract", 0)
        kept = sum(p.route == "extract" for p in res.paragraphs)
        prev = " | ".join(f"{d['score']:.0f}:{d['preview'][:30]}" for d in sel[:3])
        print(f"{th:>9.1f}{kept:>6}{len(sel):>8}{ext:>9}{len(pk.chunks):>7}{pk.est_llm_input_tokens:>8}"
              f"{sum(d['has_statistic'] for d in sel):>13}  {prev}")
    print("\nPick the highest threshold whose dropped paragraphs contain no findings "
          "(check 'drop w/ stat' and --scores).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paper", nargs="?", help="markdown file of one article")
    ap.add_argument("-o", "--out", help="write JSON result here (paragraphs, dropped, and chunks with --pack)")
    ap.add_argument("--disable", nargs="*", default=[], help="step or category names to switch off")
    ap.add_argument("--only", nargs="*", default=[], choices=[ROBUSTNESS, TOKEN_REDUCTION],
                    help="run only these categories (structure always runs)")
    ap.add_argument("--tokenizer", default="auto", help="auto | tiktoken | chars | hf:<model-name>")
    g = ap.add_argument_group("selection")
    g.add_argument("--min-score", type=float, default=Config.min_score, help="selection threshold")
    g.add_argument("--budget", type=int, default=None, help="max extract tokens per article")
    g.add_argument("--no-keep-null", action="store_true", help="do not auto-keep null-result paragraphs")
    g.add_argument("--always-keep", nargs="*", default=list(Config.always_keep_sections),
                   help="sections never dropped by selection")
    g = ap.add_argument_group("packing")
    g.add_argument("--pack", action="store_true", help="pack extract paragraphs into LLM chunks")
    g.add_argument("--max-chunk-tokens", type=int, default=PackConfig.max_chunk_tokens)
    g.add_argument("--max-paragraph-tokens", type=int, default=None)
    g.add_argument("--label", choices=["id_section", "id", "none"], default=PackConfig.label)
    g.add_argument("--prompt-overhead", type=int, default=PackConfig.prompt_overhead_tokens,
                   help="prompt tokens resent with every chunk (for estimates)")
    g.add_argument("--card-tokens", type=int, default=PackConfig.study_card_tokens)
    g.add_argument("--card-in-chunks", action="store_true", help="prepend the study card to every chunk")
    g = ap.add_argument_group("reports")
    g.add_argument("--ablation", action="store_true", help="token savings and health per step")
    g.add_argument("--sweep", nargs="*", type=float, help="report selection at these min-score values")
    g.add_argument("--scores", action="store_true", help="print the selection score of every paragraph")
    g.add_argument("--print", dest="show", action="store_true", help="print the paragraphs")
    g.add_argument("--print-chunks", action="store_true", help="print the chunk texts (implies --pack)")
    g.add_argument("--list-steps", action="store_true")
    a = ap.parse_args(argv)

    if a.list_steps:
        _print_steps()
        return 0
    if not a.paper:
        ap.error("paper is required")
    text = Path(a.paper).read_text(encoding="utf-8")
    cfg = Config(min_score=a.min_score, always_keep_sections=tuple(a.always_keep),
                 keep_null_results=not a.no_keep_null, max_extract_tokens=a.budget)
    pcfg = PackConfig(max_chunk_tokens=a.max_chunk_tokens, max_paragraph_tokens=a.max_paragraph_tokens,
                      label=a.label, prompt_overhead_tokens=a.prompt_overhead,
                      study_card_tokens=a.card_tokens, include_study_card_in_chunks=a.card_in_chunks)
    if a.ablation:
        _ablation(text, a.paper, a.tokenizer, cfg, pcfg)
        return 0
    if a.sweep is not None:
        _sweep(text, a.paper, a.tokenizer, cfg, pcfg, a.sweep or [0, 1, 2, 3, 4, 5, 6])
        return 0
    try:
        disabled = resolve_disabled(a.disable, a.only)
    except ValueError as e:
        ap.error(str(e))
    count = make_token_counter(a.tokenizer)
    res = preprocess(text, disabled=disabled, tokenizer=count, source=a.paper, config=cfg)
    _print_report(res)
    if a.scores:
        _print_scores(res)
    if a.show:
        for p in res.paragraphs:
            print(f"\n[{p.id}] {p.section}/{p.route}  ({p.n_tokens} tok, score {p.score},"
                  f" orig {p.orig_start}-{p.orig_end})  {p.heading}\n{p.text}")
    out = res.to_dict()
    if a.pack or a.print_chunks:
        pk = pack(res, pcfg, count)
        _print_pack(pk, a.print_chunks)
        out["pack"] = pk.to_dict()
        out["pack"]["split_pieces"] = [q.to_dict() for q in pk.units.values() if q.parent]
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
