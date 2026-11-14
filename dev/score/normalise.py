"""Text normalisation, synonym groups, change-direction groups and node signatures."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SYN_PATH = HERE / "synonyms.tsv"
TAXON_TABLE = ROOT / "data" / "ncbitaxon_names.tsv"

STOP = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "by", "with", "from", "as", "is", "are",
        "was", "were", "be", "per", "between", "among", "than", "that", "this", "these", "those", "its", "it", "over",
        "under", "after", "before", "during", "relative", "compared", "number", "count"}

# --- change direction -----------------------------------------------------------------------------
UP = {"increased", "introduced", "initiated"}
DOWN = {"decreased", "removed", "terminated", "interrupted", "aborted"}
OCCUR = {"present", "occurred", "ongoing"}
ABSENT = {"absent"}
CHANGE_WORDS = UP | DOWN | OCCUR | ABSENT | {"unchanged", "higher", "lower", "reduced", "suppressed", "affected", "remained",
                                             "increase", "decrease", "high", "low", "stable", "persisted"}


def direction_group(qualifier: Optional[str], null_object: bool = False) -> str:
    if null_object:
        return "NONE"          # a null result's object has no direction ("unchanged" / missing both mean "none")
    q = (qualifier or "").strip().lower()
    if q in UP:
        return "UP"
    if q in DOWN:
        return "DOWN"
    if q in OCCUR:
        return "OCCUR"
    if q in ABSENT:
        return "ABSENT"
    return "NONE"


# --- labels for ontology IDs used as measured_attribute --------------------------------------------
# Labels are what the gold nodes using that ID are about (checked against the node names in the gold files).
ATTR_LABELS: Dict[str, str] = {
    "pato:0000070": "abundance", "ncit:c53338": "density", "ncit:c25681": "size",
    "pato:0000122": "length", "pato:0000146": "temperature", "pato:0000011": "age", "pato:0001334": "diameter",
    "pato:0000915": "thickness", "pato:0000044": "frequency", "pato:0000049": "intensity", "pato:0001019": "density",
    "pato:0000082": "persistence",
    "http://purl.obolibrary.org/obo/to_0000241": "number of leaves",
    "http://purl.obolibrary.org/obo/to_0002637": "leaf size",
    "http://purl.obolibrary.org/obo/soy_0001740": "number of flowers",
    "http://purl.obolibrary.org/obo/gsso_011861": "reproductive allocation",
    "https://kos.lifewatch.eu/thesauri/traits/c_ddc0028f": "density",
    "https://kos.lifewatch.eu/thesauri/traits/c_bb852c2c": "size",
    "https://kos.lifewatch.eu/thesauri/alienspecies/c_6": "spread",
    "https://cropontology.org/rdf/co_357:1000408": "number of seedlings",
    "http://top-thesaurus.org/trait#top25": "leaf area",
    "http://www.fao.org/aims/aos/cwr.owl#populationsize": "population size",
}

_ID_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9_.\-]*:\S+|https?://\S+)$")


def is_id(s: Optional[str]) -> bool:
    return bool(s) and bool(_ID_RE.match(str(s).strip()))


# --- lemmatiser and tokeniser --------------------------------------------------------------------------
def lemma(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("sses"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith(("shes", "ches", "xes", "zes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 6 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 5 and w.endswith("ed"):
        w = w[:-2]
    return w


def _raw_tokens(text: str) -> List[str]:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return [lemma(t) for t in re.findall(r"[a-z0-9]+", text)]


@lru_cache(maxsize=4)
def load_synonyms(path: str = str(SYN_PATH)) -> Tuple[Dict[Tuple[str, ...], str], int]:
    table: Dict[Tuple[str, ...], str] = {}
    longest = 1
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            group, terms = line.split("\t", 1)
            for term in terms.split("|"):
                toks = tuple(_raw_tokens(term))
                if toks:
                    table[toks] = group.strip()
                    longest = max(longest, len(toks))
    return table, longest


def norm_tokens(text: Optional[str], syn_path: str = str(SYN_PATH)) -> Tuple[str, ...]:
    """Lower-case, lemmatise, replace synonym phrases by '@group', drop stop words."""
    if not text:
        return ()
    syn, longest = load_synonyms(syn_path)
    toks = _raw_tokens(text)
    out: List[str] = []
    i = 0
    while i < len(toks):
        for n in range(min(longest, len(toks) - i), 0, -1):
            g = syn.get(tuple(toks[i:i + n]))
            if g:
                out.append("@" + g)
                i += n
                break
        else:
            out.append(toks[i])
            i += 1
    return tuple(t for t in out if t.startswith("@") or t not in STOP)


def jaccard(a: Iterable, b: Iterable) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def overlap_coef(a: Iterable, b: Iterable) -> float:
    a, b = set(a), set(b)
    if not a or not b:
        return 1.0
    return len(a & b) / min(len(a), len(b))


# --- taxa ---------------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def taxon_tables() -> Tuple[Dict[str, FrozenSet[Tuple[str, str]]], FrozenSet[Tuple[str, str]], FrozenSet[str]]:
    """(taxid -> binomial keys, all known binomial keys, known full lower-case binomials)."""
    by_id: Dict[str, set] = {}
    keys, full = set(), set()
    if TAXON_TABLE.exists():
        for line in TAXON_TABLE.read_text(encoding="utf-8").splitlines()[1:]:
            a = line.split("\t")
            if len(a) == 2 and len(a[0].split()) == 2:
                g, e = a[0].lower().split()
                keys.add((g[0], e))
                full.add(a[0].lower())
                by_id.setdefault("NCBITaxon:" + a[1], set()).add((g[0], e))
    return {k: frozenset(v) for k, v in by_id.items()}, frozenset(keys), frozenset(full)


_BINOM = re.compile(r"\b([A-Z][a-z]{2,})\s+(?:×\s*)?([a-z]{3,})\b")
_ABBR = re.compile(r"\b([A-Z])\.\s?([a-z]{3,})\b")
_PLAIN_BINOM = re.compile(r"^[A-Z][a-z]{2,}\s+[a-z]{3,}$")


def find_binomials(text: str) -> Tuple[FrozenSet[Tuple[str, str]], str]:
    """Binomial keys (genus initial, epithet) found in `text`, and `text` with them removed."""
    _, keys, full = taxon_tables()
    found = set()
    spans = []
    for m in _BINOM.finditer(text):
        if f"{m.group(1)} {m.group(2)}".lower() in full:
            found.add((m.group(1)[0].lower(), m.group(2)))
            spans.append(m.span())
    for m in _ABBR.finditer(text):
        k = (m.group(1).lower(), m.group(2))
        if k in keys:
            found.add(k)
            spans.append(m.span())
    for a, b in sorted(spans, reverse=True):
        text = text[:a] + " " + text[b:]
    return frozenset(found), text


def taxon_ids_in(term: Optional[str]) -> FrozenSet[str]:
    if term and str(term).startswith("NCBITaxon:"):
        return frozenset([str(term).strip()])
    return frozenset()


# --- node signature ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class NodeSig:
    id: str
    name: str
    taxa_ids: FrozenSet[str]
    primary_taxon: Optional[str]
    taxa_text: FrozenSet[Tuple[str, str]]
    entity_text: FrozenSet[str]
    attribute: Optional[str]                  # raw measured_attribute
    attr_id: Optional[str]                    # lower-cased ID when measured_attribute is an ID
    attr_label: Optional[str]                 # label for a known ID, or the text itself
    attr_tokens: FrozenSet[str]               # tokens of the attribute label/text only (empty for an unlabelled ID)
    attr_groups: FrozenSet[str]
    name_tokens: FrozenSet[str]               # node name minus taxa / change words (descriptor fallback)
    attr_known: bool
    life_stage: Optional[str]
    direction: str
    qualifier: Optional[str]
    entity_type: Optional[str]

    @property
    def has_taxon(self) -> bool:
        return bool(self.taxa_ids or self.taxa_text)

    @property
    def descriptor(self) -> FrozenSet[str]:
        """Everything the node says about its variable: attribute + entity text (+ name when the attribute ID is unlabelled)."""
        d = self.attr_tokens | self.entity_text
        return d | self.name_tokens if (self.attr_id and not self.attr_known) else d

    def key(self) -> tuple:
        return (self.taxa_ids, self.taxa_text, self.entity_text, self.attr_id or self.attr_tokens, self.direction)


def _collect_taxa(node: dict) -> Tuple[FrozenSet[str], Optional[str]]:
    ids: List[str] = []
    prim = None
    et = node.get("entity_term")
    if taxon_ids_in(et):
        ids.append(str(et).strip())
        prim = str(et).strip()
    for a in node.get("applied_to") or []:
        t = a.get("entity_term") if isinstance(a, dict) else None
        if taxon_ids_in(t):
            ids.append(str(t).strip())
            prim = prim or str(t).strip()
    return frozenset(ids), prim


def node_sig(node: dict, null_object: bool = False, extra_taxa: Iterable[str] = ()) -> NodeSig:
    """`extra_taxa`: NCBITaxon IDs from the owning edge's dose.counted_entity."""
    ids, prim = _collect_taxa(node)
    extra = frozenset(extra_taxa)
    ids = ids | extra
    prim = prim or (sorted(extra)[0] if extra else None)
    by_id, _, _ = taxon_tables()
    name = str(node.get("name") or "")
    et = node.get("entity_term")
    et_text = None if (et is None or is_id(str(et))) else str(et).strip()
    keys = set()
    for i in ids:
        keys |= set(by_id.get(i, ()))
    # entity_text: the free-text entity_term, or the node name; taxon names and change words removed
    base = et_text if et_text and not _PLAIN_BINOM.match(et_text) else name
    if et_text and _PLAIN_BINOM.match(et_text):
        keys.add((et_text.split()[0][0].lower(), et_text.split()[1].lower()))   # entity_term is exactly a binomial
    found, rest = find_binomials(base)
    keys |= set(found)
    found_n, _ = find_binomials(name)
    keys |= set(found_n)
    rest = re.sub(r"\(.*?\)", " ", rest)
    rest_tokens = [t for t in re.findall(r"[A-Za-z0-9\-]+", rest) if t.lower() not in CHANGE_WORDS]
    entity_text = frozenset(norm_tokens(" ".join(rest_tokens)))
    # name without taxa / change words, used when a measured_attribute ID has no known label
    _, name_rest = find_binomials(name)
    name_tokens = frozenset(norm_tokens(" ".join(t for t in re.findall(r"[A-Za-z0-9\-]+", re.sub(r"\(.*?\)", " ", name_rest))
                                                 if t.lower() not in CHANGE_WORDS)))
    attr = node.get("measured_attribute")
    attr = None if attr in (None, "") else str(attr).strip()
    attr_id = attr.lower() if is_id(attr) else None
    label = ATTR_LABELS.get(attr_id) if attr_id else attr
    known = not (attr_id and not label)
    toks = frozenset(norm_tokens(label)) if label else frozenset()   # an unlabelled ID has no tokens of its own
    groups = frozenset(t for t in toks if t.startswith("@"))
    q = node.get("state_or_change_qualifier")
    return NodeSig(id=str(node.get("id")), name=name, taxa_ids=ids, primary_taxon=prim, taxa_text=frozenset(keys),
                   entity_text=entity_text, attribute=attr, attr_id=attr_id, attr_label=label, attr_tokens=frozenset(toks),
                   attr_groups=groups, name_tokens=name_tokens, attr_known=known, life_stage=node.get("life_stage"), direction=direction_group(q, null_object),
                   qualifier=q, entity_type=node.get("entity_type"))
