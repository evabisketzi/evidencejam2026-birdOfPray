#!/usr/bin/env python3
"""
ground_terms.py - ground free-text terms in LLM-generated CAMO output to ontology CURIEs.

Reads the JSON/YAML produced by the extraction step (a CAMO CausalGraph, a list of nodes, or
any structure containing them), finds every groundable field that still holds free text, and
looks it up in local ontology indexes chosen by the kind of field.

The LLM never writes an ID. Extraction writes names; this script finds candidates; a unique
exact label / exact-synonym match is assigned here; anything ambiguous or fuzzy is left for
select_terms.py, where the LLM picks a candidate *number*; anything else stays free text
(except `unit`, whose schema pattern only accepts unit:/UO: CURIEs - unmatched units move to
`unit_text`).

Fields grounded (anywhere in the document: nodes, applied_to, composition members,
components.counted_entity, quantity values):

  entity_term         searched in the sources for its entity_type
  measured_attribute  PATO (quality branch), ELMO
  life_stage_term     PO, UBERON (when their indexes have been built)
  unit                curated QUDT / UO table (ontology_index/units.yaml)

Sources are the gzipped JSON indexes in ontology_index/, built once with
build_ontology_indexes.py and committed. A run needs no OAK, no network and no downloads.
For development, a source in DEFAULT_CONFIG can instead be any OAK adapter
({"adapter": "sqlite:obo:foo"}); it is converted to the same term table and cached under
~/.cache/ground_terms.

Taxa: NCBITaxon (pruned to the taxa named in the corpus, plus their lineage). Names not in
the lexicon fall back to fuzzy-within-genus, then genus only, then (with --taxon-online)
NCBI E-utilities, whose answers are cached in ontology_index/taxon_online_cache.json.

Outputs
  --report (always)  one entry per unique (kind, text): status, selected CURIE, ranked
                     candidates with source, label, definition, parents (taxa: rank and
                     lineage), node names and source spans - the input for select_terms.py.
                     Also lists CURIEs that were already in the input, checked to exist and
                     flagged when their label doesn't resemble the node's name.
  --out (optional)   a copy of the document with resolved CURIEs written into their fields
                     and unmatched units moved to unit_text.

Status values
  resolved      exactly one label / exact-synonym match across the searched sources, or
                exactly one in the preferred (first-listed) source when other sources
                also match exactly ("resolution" says which)
  ambiguous     several label / exact-synonym matches (homonyms, shared synonyms)
  needs_review  only related/broad/narrow-synonym, head-noun, fuzzy, genus-level or online
                candidates
  no_match      nothing found

Usage
  python ground_terms.py llm_output.json --report report.json --out grounded.json
  python ground_terms.py llm_output.yaml --kinds taxon measured_attribute   # subset

In code (load the indexes once, ground many articles):
  registry = Registry(load_config(), Prefixes(CAMO_PREFIXES))
  report = ground_graph(doc, registry)
  grounded = apply_groundings(doc, report, selections={})

Requires: rapidfuzz, pyyaml, curies.  (oaklib only for "adapter:" sources.)
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import curies
import yaml
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent
INDEX_DIR = ROOT / "ontology_index"
CACHE_DIR = Path.home() / ".cache" / "ground_terms"

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "index_dir": str(INDEX_DIR),
    "sources": {
        "ncbitaxon": {"index": "ncbitaxon.json.gz"},
        "elmo": {"index": "elmo.json.gz"},
        "envo": {"index": "envo.json.gz"},
        "go": {"index": "go.json.gz"},
        "pato": {"index": "pato.json.gz"},
        "chebi": {"index": "chebi.json.gz"},
        "po": {"index": "po.json.gz"},
        "uberon": {"index": "uberon.json.gz"},
        "units": {"units": "units.yaml"},
    },
    # which sources are searched for which kind of field (order = preference in the report)
    "kinds": {
        "taxon": ["ncbitaxon"],
        "environmental_variable": ["elmo", "envo", "chebi"],
        "composite_variable": ["elmo", "envo"],
        "environmental_process": ["elmo", "go", "envo"],
        "management_intervention": ["elmo"],
        "untyped": ["elmo", "envo", "ncbitaxon"],     # entity_term with no entity_type
        "measured_attribute": ["pato", "elmo"],
        "life_stage": ["po", "uberon"],
        "unit": ["units"],
    },
    # field name -> kind ("@entity_type" = use the object's entity_type, or "untyped")
    "fields": {
        "entity_term": "@entity_type",
        "measured_attribute": "measured_attribute",
        "life_stage_term": "life_stage",
        "unit": "unit",
    },
}

# CAMO 0.10 prefixes (used when --schema is not given)
CAMO_PREFIXES = {
    "elmo": "https://w3id.org/elmo/elmo_", "elmo_cas": "https://w3id.org/elmo/cas/",
    "ENVO": "http://purl.obolibrary.org/obo/ENVO_", "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    "GO": "http://purl.obolibrary.org/obo/GO_", "PATO": "http://purl.obolibrary.org/obo/PATO_",
    "ECO": "http://purl.obolibrary.org/obo/ECO_", "BFO": "http://purl.obolibrary.org/obo/BFO_",
    "UO": "http://purl.obolibrary.org/obo/UO_", "unit": "http://qudt.org/vocab/unit/",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_", "PO": "http://purl.obolibrary.org/obo/PO_",
    "UBERON": "http://purl.obolibrary.org/obo/UBERON_", "STATO": "http://purl.obolibrary.org/obo/STATO_",
    "OBI": "http://purl.obolibrary.org/obo/OBI_", "IAO": "http://purl.obolibrary.org/obo/IAO_",
    "NCIT": "http://purl.obolibrary.org/obo/NCIT_", "ECSO": "http://purl.dataone.org/odo/ECSO_",
    "wd": "http://www.wikidata.org/entity/",
}

# Paste into the extraction prompt: the grounding step relies on these.
EXTRACTION_RULES = """\
Ontology fields - write NAMES, never IDs or CURIEs:
- entity_term: the plain name of the entity. Taxa: the full scientific name as the paper
  gives it (e.g. "Alliaria petiolata", not "A. petiolata", "garlic mustard" or an ID).
  Variables, processes and interventions: a short noun phrase ("soil pH", "seeding",
  "prescribed burning").
- measured_attribute: the bare attribute ("density", "cover", "species richness",
  "biomass"), without the entity or the life stage.
- life_stage / life_stage_term: the stage, kept out of measured_attribute.
- unit: the unit exactly as written ("kg/ha", "%", "ramets/m2").
- Always set entity_type (taxon, environmental_variable, composite_variable,
  environmental_process, management_intervention); it decides which ontologies are searched.
"""


def load_config() -> dict:
    """A fresh copy of DEFAULT_CONFIG. There is no config file: to change sources or
    routing, edit DEFAULT_CONFIG above."""
    return copy.deepcopy(DEFAULT_CONFIG)


class Prefixes:
    """Converts whatever a source returns (CURIE in any casing, or IRI) to CAMO's form."""

    def __init__(self, prefix_map: dict[str, str]):
        self.map = dict(prefix_map)
        self.lower = {p.lower(): p for p in self.map}
        self.converter = curies.Converter.from_prefix_map(self.map)

    def to_camo(self, ident: str) -> str:
        if ident.startswith(("http://", "https://")):
            return self.converter.compress(ident) or ident
        prefix, _, local = ident.partition(":")
        if prefix in self.map:
            return ident
        if prefix.lower() in self.lower:
            return f"{self.lower[prefix.lower()]}:{local}"
        iri = f"http://purl.obolibrary.org/obo/{prefix}_{local}"          # OBO default pattern
        return self.converter.compress(iri) or ident

    def prefix_of(self, camo_curie: str) -> str:
        return camo_curie.split(":", 1)[0] if ":" in camo_curie and not camo_curie.startswith("http") else ""

    def is_curie(self, value: str) -> bool:
        prefix, sep, local = value.partition(":")
        return bool(sep) and prefix.lower() in self.lower and bool(local) and " " not in value


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def match_type_for(pred: str) -> str:
    """Map a label/synonym predicate to the match_type reported for a hit."""
    if pred in ("rdfs:label", "label"):
        return "label"
    for marker, name in (("Exact", "exact_synonym"), ("Related", "related_synonym"),
                         ("Narrow", "narrow_synonym"), ("Broad", "broad_synonym")):
        if marker in pred:
            return name
    return "alt_label"                                     # skos:altLabel, IAO alternative label


# Only these count as exact enough to resolve a term automatically.
AUTO_RESOLVE = {"label", "exact_synonym", "alt_label"}
MATCH_RANK = ["label", "exact_synonym", "alt_label", "common_name", "related_synonym",
              "narrow_synonym", "broad_synonym"]


def rank_of(match_type: str) -> int:
    return MATCH_RANK.index(match_type) if match_type in MATCH_RANK else len(MATCH_RANK)


def norm_key(text: str) -> str:
    text = re.sub(r"<[^>]+>|[*_]", " ", text.lower())
    text = re.sub(r"[^\w\s/-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def singular(text: str) -> str:
    words = text.split(" ")
    w = words[-1]
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    return " ".join(words[:-1] + [w])


RANK_MARKERS = {"subsp.", "ssp.", "var.", "f.", "forma", "subvar."}
DROP_TOKENS = {"cf.", "cf", "aff.", "aff", "nr.", "s.l.", "s.str.", "sensu", "lato", "stricto"}
GENUS_RE = re.compile(r"^[A-Z][a-z]+$")
ABBREV_GENUS_RE = re.compile(r"^[A-Z]\.$")
EPITHET_RE = re.compile(r"^[a-z][a-z-]+$")


def normalise_taxon(raw: str) -> str:
    text = re.sub(r"<[^>]+>|[*_]", "", raw)
    text = re.sub(r"\s+", " ", text).strip(" .,;:")
    tokens = [t for t in text.split(" ") if t.lower() not in DROP_TOKENS]
    if not tokens:
        return text
    if not (GENUS_RE.match(tokens[0]) or ABBREV_GENUS_RE.match(tokens[0])):
        return " ".join(tokens)                                    # common name
    kept, i = [tokens[0]], 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("sp.", "spp.", "sp", "spp"):
            break
        if EPITHET_RE.match(tok):
            kept.append(tok)
        elif tok in RANK_MARKERS and i + 1 < len(tokens) and EPITHET_RE.match(tokens[i + 1]):
            kept += ["subsp." if tok == "ssp." else tok, tokens[i + 1]]
            i += 1
        else:
            break                                                  # authority, year, ...
        i += 1
    return " ".join(kept)


def expand_abbreviation(name: str, doc_text: str) -> str:
    parts = name.split(" ")
    if len(parts) < 2 or not ABBREV_GENUS_RE.match(parts[0]):
        return name
    genera = set(re.findall(rf"\b({parts[0][0]}[a-z]+)\s+{re.escape(parts[1])}\b", doc_text))
    return " ".join([genera.pop()] + parts[1:]) if len(genera) == 1 else name


def norm_unit(text: str) -> str:
    text = text.strip().replace("²", "2").replace("³", "3").replace("⁻¹", "-1").replace("⁻", "-")
    text = text.replace("µ", "u").replace("μ", "u").replace("·", " ").replace("°", "deg")
    return re.sub(r"\s+", " ", text)


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------

class IndexSource:
    """Lexical / taxon search over a term table {CURIE: {l, s, d, p | r, pa}}."""

    def __init__(self, name: str, data: dict):
        self.name = name
        self.strategy = data.get("strategy", "lexical")
        self.terms: dict[str, dict] = data["terms"]
        self.prefixes = set(data.get("prefixes", []))
        self.subset = bool(data.get("subset"))                 # pruned: absence proves nothing
        self.version = "; ".join(data.get("versions", []))
        suffixes = [" " + s for s in data.get("strip_suffixes", [])]
        self.strings: dict[str, dict[str, tuple[str, str]]] = {}
        for curie, term in self.terms.items():
            for text, mtype in [(term["l"], "label")] + [tuple(s) for s in term.get("s", [])]:
                key = norm_key(text)
                keys = {key, singular(key)}
                for suf in suffixes:
                    if key.endswith(suf) and len(key) > len(suf) + 2:
                        base = key[: -len(suf)]
                        keys |= {base, singular(base)}
                for k in keys:
                    if k:
                        self._add(k, curie, mtype, text)
        self.keys = [k for k in self.strings if len(k) >= 3]       # fuzzy pool: no "h", "s"
        self.children: dict[str, list[str]] = defaultdict(list)
        for curie, term in self.terms.items():
            if term.get("pa"):
                self.children[term["pa"]].append(curie)

    def _add(self, key: str, curie: str, mtype: str, text: str) -> None:
        slot = self.strings.setdefault(key, {})
        if curie not in slot or rank_of(mtype) < rank_of(slot[curie][0]):
            slot[curie] = (mtype, text)

    # ---- term details ---------------------------------------------------
    def has(self, curie: str) -> bool:
        return curie in self.terms

    def label(self, curie: str) -> str:
        return self.terms.get(curie, {}).get("l", "")

    def names(self, curie: str) -> list[str]:
        term = self.terms.get(curie, {})
        return [term.get("l", "")] + [s[0] for s in term.get("s", [])]

    def lineage(self, curie: str) -> list[str]:
        ranks = ("realm", "domain", "superkingdom", "kingdom", "phylum", "class", "order", "family", "genus")
        out, labels, seen = [], [], set()
        node = self.terms.get(curie, {}).get("pa")
        while node and node not in seen and len(seen) < 80:
            seen.add(node)
            term = self.terms.get(node)
            if term is None:
                break
            labels.append(term["l"])
            if term.get("r") in ranks:
                out.append(f"{term['r']}: {term['l']}")
            node = term.get("pa")
        if not out:
            out = [lbl for lbl in labels if lbl and lbl != "cellular organisms"][:6]
        return list(reversed(out))

    def candidate(self, curie: str, match_type: str, score: float, matched: str = "") -> dict:
        term = self.terms[curie]
        cand = {"curie": curie, "source": self.name, "label": term["l"], "match_type": match_type,
                "matched_text": matched or term["l"], "score": round(score, 1)}
        if self.strategy == "taxon":
            cand.update({"rank": term.get("r", ""), "lineage": self.lineage(curie)})
        else:
            cand.update({"definition": term.get("d", ""), "parents": term.get("p", [])})
        return cand

    # ---- search -----------------------------------------------------------
    def exact(self, text: str) -> dict[str, tuple[str, str]]:
        key = norm_key(text)
        hits: dict[str, tuple[str, str]] = {}
        for k in dict.fromkeys([key, singular(key)]):
            for curie, (mtype, original) in self.strings.get(k, {}).items():
                if curie not in hits or rank_of(mtype) < rank_of(hits[curie][0]):
                    hits[curie] = (mtype, original)
        return hits

    def search(self, text: str, top_k: int, cutoff: float, ctx: dict) -> list[dict]:
        if self.strategy == "taxon":
            return self._search_taxon(text, top_k, cutoff, ctx)
        return self._search_lexical(text, top_k, cutoff)

    def _ranked(self, hits: dict[str, tuple[str, str]], score: float, as_type: str | None = None) -> list[dict]:
        items = sorted(hits.items(), key=lambda kv: rank_of(kv[1][0]))
        return [self.candidate(c, as_type or mt, score, orig) for c, (mt, orig) in items]

    def _search_lexical(self, text: str, top_k: int, cutoff: float) -> list[dict]:
        hits = self.exact(text)
        if hits:
            return self._ranked(hits, 100.0)[:top_k]
        q = norm_key(text)
        best: dict[str, dict] = {}
        tokens = q.split(" ")
        for i in range(1, len(tokens)):                            # head-noun backoff
            sub = " ".join(tokens[i:])
            if len(sub) < 4:
                break
            sub_hits = self.exact(sub)
            if sub_hits:
                for cand in self._ranked(sub_hits, 85.0, "head_noun"):
                    best[cand["curie"]] = cand
                break
        # token_sort_ratio: tolerates typos and word order, but not substring matches
        # (WRatio's partial matching scored "richness" vs "h" at 90)
        for key, score, _ in process.extract(q, self.keys, scorer=fuzz.token_sort_ratio,
                                             limit=top_k * 4, score_cutoff=cutoff):
            for curie, (_, original) in self.strings[key].items():
                if curie not in best or best[curie]["score"] < score:
                    best[curie] = self.candidate(curie, "fuzzy", score, original)
        return sorted(best.values(), key=lambda c: -c["score"])[:top_k]

    def _search_taxon(self, text: str, top_k: int, cutoff: float, ctx: dict) -> list[dict]:
        query = ctx.get("taxon_query", text)
        hits = self.exact(query)
        if hits:
            return self._ranked(hits, 100.0)[:top_k]
        cands: list[dict] = []
        parts = query.split(" ")
        if len(parts) >= 2 and GENUS_RE.match(parts[0]):
            genera = [c for c in self.exact(parts[0]) if self.terms[c].get("r") == "genus"] \
                or list(self.exact(parts[0]))
            for genus in genera:
                kids = {self.terms[k]["l"]: k for k in self.children.get(genus, [])}
                for lbl, score, _ in process.extract(query, list(kids), scorer=fuzz.ratio,
                                                     limit=top_k, score_cutoff=max(cutoff, 85)):
                    cands.append(self.candidate(kids[lbl], "fuzzy_within_genus", score, lbl))
        else:
            for key, score, _ in process.extract(norm_key(query), self.keys, scorer=fuzz.ratio,
                                                 limit=top_k, score_cutoff=max(cutoff, 90)):
                for curie, (_, original) in self.strings[key].items():
                    cands.append(self.candidate(curie, "fuzzy", score, original))
        if not cands and ctx.get("online") is not None:
            cands = ctx["online"].lookup(query)
        if not cands and len(parts) >= 2 and GENUS_RE.match(parts[0]):
            for genus in self.exact(parts[0]):
                cands.append(self.candidate(genus, "genus_only", 50.0, parts[0]))
        return sorted(cands, key=lambda c: -c["score"])[:top_k]


class UnitSource:
    """Exact lookup in the curated unit table; never fuzzy (a wrong unit is worse than none)."""

    strategy = "units"
    subset = False

    def __init__(self, name: str, path: Path):
        self.name = name
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.terms = {curie: {"l": entry["label"], "s": [[a, "exact_synonym"] for a in entry.get("aliases", [])]}
                      for curie, entry in data.items()}
        self.prefixes = {c.split(":", 1)[0] for c in self.terms}
        self.version = path.name
        self.exact_map: dict[str, set[str]] = defaultdict(set)
        self.fold_map: dict[str, set[str]] = defaultdict(set)
        for curie, term in self.terms.items():
            for text in [term["l"]] + [s[0] for s in term["s"]]:
                for form in {norm_unit(text), norm_unit(text).replace(" ", "")}:
                    self.exact_map[form].add(curie)
                    self.fold_map[form.lower()].add(curie)

    def has(self, curie: str) -> bool:
        return curie in self.terms

    def label(self, curie: str) -> str:
        return self.terms.get(curie, {}).get("l", "")

    def names(self, curie: str) -> list[str]:
        return [self.label(curie)] + [s[0] for s in self.terms.get(curie, {}).get("s", [])]

    def search(self, text: str, top_k: int, cutoff: float, ctx: dict) -> list[dict]:
        form = norm_unit(text)
        hits = set()
        for f in (form, form.replace(" ", "")):
            hits |= self.exact_map.get(f, set())
        if not hits:
            for f in (form.lower(), form.replace(" ", "").lower()):
                hits |= self.fold_map.get(f, set())
        return [{"curie": c, "source": self.name, "label": self.label(c), "match_type": "label",
                 "matched_text": text, "score": 100.0} for c in sorted(hits)][:top_k]


class OnlineTaxa:
    """NCBI E-utilities fallback for taxa missing from the pruned lexicon, with a JSON cache.

    With online=False only the cache is consulted, so a committed cache keeps judge runs
    offline. Sends no personal data: a generic tool name and the taxon name only."""

    URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def __init__(self, cache_path: Path, online: bool):
        self.path, self.online = cache_path, online
        self.cache: dict[str, list[dict]] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        self.dirty = False
        self._last = 0.0

    def _get(self, endpoint: str, params: dict) -> dict:
        wait = 0.34 - (time.time() - self._last)                   # NCBI: 3 requests/s without key
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        params = {**params, "retmode": "json", "tool": "camo_grounder"}
        with urllib.request.urlopen(self.URL + endpoint + "?" + urllib.parse.urlencode(params), timeout=5) as r:
            return json.load(r)

    def lookup(self, name: str) -> list[dict]:
        key = name.lower()
        if key not in self.cache:
            if not self.online:
                return []
            try:
                ids = self._get("esearch.fcgi", {"db": "taxonomy", "term": f'"{name}"[All Names]',
                                                 "retmax": 5})["esearchresult"].get("idlist", [])
                found = []
                if ids:
                    summary = self._get("esummary.fcgi", {"db": "taxonomy", "id": ",".join(ids)})["result"]
                    for tid in ids:
                        s = summary.get(tid, {})
                        found.append({"curie": f"NCBITaxon:{tid}", "label": s.get("scientificname", ""),
                                      "rank": s.get("rank", ""), "division": s.get("division", ""),
                                      "common_name": s.get("commonname", "")})
                self.cache[key] = found
                self.dirty = True
            except Exception as exc:                               # offline, timeout, bad reply
                print(f"  NCBI lookup failed for {name!r}: {exc}", file=sys.stderr)
                return []
        out = []
        for hit in self.cache[key]:
            exact = hit["label"].lower() == key
            out.append({"curie": hit["curie"], "source": "ncbi_online", "label": hit["label"],
                        "match_type": "label" if exact and len(self.cache[key]) == 1 else "ncbi_online",
                        "matched_text": name, "score": 95.0 if exact else 80.0, "rank": hit["rank"],
                        "lineage": [f"division: {hit['division']}"] if hit.get("division") else []})
        return out

    def save(self) -> None:
        if self.dirty:
            self.path.write_text(json.dumps(self.cache, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
            self.dirty = False


def terms_from_oak(name: str, spec: dict, px: Prefixes, rebuild: bool = False) -> dict:
    """Build a term table from any OAK adapter (development only; cached)."""
    key = hashlib.sha1(json.dumps([spec.get("adapter"), spec.get("roots"), spec.get("prefixes")],
                                  sort_keys=True).encode()).hexdigest()[:12]
    path = CACHE_DIR / f"{name}-{key}.json.gz"
    if path.exists() and not rebuild:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    from oaklib import get_adapter
    from oaklib.datamodels.vocabulary import IS_A, LABEL_PREDICATE

    print(f"Building term table for {name} from OAK ({spec['adapter']}); cached afterwards", file=sys.stderr)
    adapter = get_adapter(spec["adapter"])
    allowed = set(spec.get("prefixes", []))
    keep = set(adapter.descendants(spec["roots"], predicates=[IS_A], reflexive=True)) if spec.get("roots") else None
    try:
        obsolete = set(adapter.obsoletes())
    except Exception:
        obsolete = set()
    terms = {}
    for native in adapter.entities(filter_obsoletes=False):
        if native in obsolete or (keep is not None and native not in keep):
            continue
        curie = px.to_camo(native)
        label = adapter.label(native)
        if px.prefix_of(curie) not in allowed or not label:
            continue
        syns = [[v, match_type_for(pred)] for pred, vals in (adapter.entity_alias_map(native) or {}).items()
                if pred != LABEL_PREDICATE for v in vals if v]
        try:
            definition = adapter.definition(native) or ""
        except Exception:
            definition = ""
        parents = [adapter.label(p) for p in adapter.hierarchical_parents(native) if not p.startswith("_:")]
        terms[curie] = {"l": label, "s": syns, "d": definition[:200], "p": [p for p in parents if p][:3]}
    data = {"source": name, "strategy": spec.get("strategy", "lexical"), "prefixes": sorted(allowed),
            "versions": [spec["adapter"]], "terms": terms}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


class Registry:
    """Loads sources lazily, so a run only opens the indexes it needs."""

    def __init__(self, config: dict, prefixes: Prefixes, rebuild_cache: bool = False,
                 taxon_online: bool = False):
        self.config, self.px, self.rebuild = config, prefixes, rebuild_cache
        self.index_dir = Path(config.get("index_dir") or INDEX_DIR)
        self._loaded: dict[str, Any] = {}
        self.online = OnlineTaxa(self.index_dir / "taxon_online_cache.json", taxon_online)

    def get(self, name: str):
        if name in self._loaded:
            return self._loaded[name]
        spec = self.config["sources"].get(name)
        src = None
        try:
            if spec is None:
                print(f"WARNING: no source named {name!r} in config", file=sys.stderr)
            elif "units" in spec:
                src = UnitSource(name, self.index_dir / spec["units"])
            elif "adapter" in spec:
                src = IndexSource(name, terms_from_oak(name, spec, self.px, self.rebuild))
            else:
                path = Path(spec["index"])
                path = path if path.is_absolute() else self.index_dir / path
                if path.exists():
                    with gzip.open(path, "rt", encoding="utf-8") as fh:
                        src = IndexSource(name, json.load(fh))
                else:
                    print(f"WARNING: index {path} not built; source {name!r} skipped, so its terms "
                          f"stay free text. Build it: python build_ontology_indexes.py --only {name}"
                          + (" (reads raw_json/ncbitaxon.json)" if name == "ncbitaxon" else ""),
                          file=sys.stderr)
        except Exception as exc:
            print(f"WARNING: could not open {name}: {exc}. Skipping it.", file=sys.stderr)
        self._loaded[name] = src
        return src

    def for_kind(self, kind: str) -> list:
        return [s for s in (self.get(n) for n in self.config["kinds"].get(kind, [])) if s]

    def for_curie(self, camo_curie: str) -> list:
        prefix = self.px.prefix_of(camo_curie)
        out = []
        for name in self.config["sources"]:
            src = self.get(name)
            if src is not None and prefix in src.prefixes:
                out.append(src)
        return out

    def versions(self) -> dict[str, str]:
        return {n: s.version for n, s in self._loaded.items() if s is not None}


# --------------------------------------------------------------------------
# Walking the LLM output
# --------------------------------------------------------------------------

def walk(obj: Any, fields: dict, path: tuple = (), ctx_spans: list | None = None,
         ctx_name: str = "") -> Iterator[dict]:
    """Yield one record per groundable field value."""
    if isinstance(obj, dict):
        spans = [s.get("text") for s in obj.get("source_spans") or [] if isinstance(s, dict) and s.get("text")]
        spans = spans or (ctx_spans or [])
        name = obj.get("name") if isinstance(obj.get("name"), str) else ctx_name
        for field, kind_rule in fields.items():
            value = obj.get(field)
            if isinstance(value, str) and value.strip() and not value.strip().startswith(("http://", "https://")):
                kind = (obj.get("entity_type") or "untyped") if kind_rule == "@entity_type" else kind_rule
                yield {"path": path, "field": field, "value": value.strip(), "kind": kind,
                       "context": spans, "node_name": name}
        for key, value in obj.items():
            if key not in ("source_spans", "embedding_vector", "embedding_text"):
                yield from walk(value, fields, path + (key,), spans, name)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from walk(item, fields, path + (i,), ctx_spans, ctx_name)


def all_strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k != "embedding_vector":
                yield from all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_strings(v)


def get_at(doc: Any, path: list | tuple) -> Any:
    target = doc
    for key in path:
        target = target[key]
    return target


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------

def decide(cands: list[dict], source_order: list[str] | None = None) -> tuple[str, str | None, str]:
    """(status, selected CURIE, how). Several exact matches from *different* ontologies are
    usually the same concept (ELMO "air temperature" / ENVO "temperature of air"): take the
    first source in the kind's order if it has exactly one. Several exact matches within one
    ontology are real homonyms and stay ambiguous."""
    exact = [c for c in cands if c["match_type"] in AUTO_RESOLVE]
    curies_ = {c["curie"] for c in exact}
    if len(curies_) == 1:
        return "resolved", curies_.pop(), "unique_exact"
    if len(curies_) > 1:
        by_source: dict[str, set] = defaultdict(set)
        for c in exact:
            by_source[c["source"]].add(c["curie"])
        for name in source_order or []:
            if name in by_source:
                if len(by_source[name]) == 1 and len(by_source) > 1:
                    return "resolved", next(iter(by_source[name])), f"preferred_source:{name}"
                break
        return "ambiguous", None, ""
    return ("needs_review", None, "") if cands else ("no_match", None, "")


def check_existing(rec: dict, registry: Registry, px: Prefixes, threshold: float) -> dict:
    curie = px.to_camo(rec["value"])
    out = {"curie": curie, "field": rec["field"], "kind": rec["kind"],
           "location": list(rec["path"]), "node_name": rec["node_name"]}
    sources = registry.for_curie(curie)
    if not sources:
        out["status"] = "not_checked (no configured source for this prefix)"
        return out
    for src in sources:
        if src.has(curie):
            names = [n for n in src.names(curie) if n]
            name = (rec["node_name"] or "").lower()
            sim = max((fuzz.partial_ratio(n.lower(), name) for n in names), default=0) if name else None
            out.update({"status": "ok", "label": src.label(curie), "source": src.name, "name_similarity": sim})
            if sim is not None and sim < threshold:
                out["status"] = "check_label (label does not resemble the node name)"
            return out
    if all(src.subset for src in sources):
        out["status"] = "not_checked (not in the local subset of this ontology)"
    else:
        out["status"] = "not_found (CURIE does not exist in the configured ontology, or is obsolete)"
    return out


def term_key(group: dict) -> str:
    return f"{group['kind']}|{group['query']}"


def ground_graph(doc: Any, registry: Registry, kinds: list[str] | None = None, top_k: int = 10,
                 fuzzy_cutoff: float = 80.0, skip_untyped: bool = False,
                 name_check_threshold: float = 60.0, verbose: bool = True) -> dict:
    """Ground every free-text field in `doc`. Returns the report (doc is not modified)."""
    config, px = registry.config, registry.px
    doc_text = "\n".join(all_strings(doc))
    groups: dict[tuple, dict] = {}
    existing: list[dict] = []
    for rec in walk(doc, config["fields"]):
        if kinds and rec["kind"] not in kinds:
            continue
        if rec["kind"] == "untyped" and skip_untyped:
            continue
        if px.is_curie(rec["value"]):
            existing.append(rec)
            continue
        if rec["kind"] not in config["kinds"]:
            print(f"WARNING: no sources configured for kind {rec['kind']!r}; skipping {rec['value']!r}",
                  file=sys.stderr)
            continue
        text = rec["value"]
        if rec["kind"] == "taxon":
            text = expand_abbreviation(normalise_taxon(text), doc_text)
        g = groups.setdefault((rec["kind"], text), {"kind": rec["kind"], "query": text, "mentions": [],
                                                     "node_names": [], "locations": [], "context": []})
        if rec["value"] not in g["mentions"]:
            g["mentions"].append(rec["value"])
        if rec["node_name"] and rec["node_name"] not in g["node_names"]:
            g["node_names"].append(rec["node_name"])
        g["locations"].append({"path": list(rec["path"]), "field": rec["field"]})
        for s in rec["context"]:
            if s not in g["context"]:
                g["context"].append(s)

    if verbose:
        print(f"{len(groups)} unique terms to ground, {len(existing)} existing CURIEs to check", file=sys.stderr)
    for (kind, text), g in groups.items():
        cands: list[dict] = []
        ctx = {"taxon_query": text, "online": registry.online}
        sources = registry.for_kind(kind)
        for src in sources:
            cands += src.search(text, top_k, fuzzy_cutoff, ctx)
        cands.sort(key=lambda c: (-c["score"], rank_of(c["match_type"])))
        g["status"], g["selected"], g["resolution"] = decide(cands, [s.name for s in sources])
        g["candidates"] = cands[:top_k]
        g["key"] = term_key(g)
        if verbose:
            print(f"  {g['status']:<13} [{kind}] {text!r} -> {g['selected'] or '-'}", file=sys.stderr)
    registry.online.save()

    checked = [check_existing(rec, registry, px, name_check_threshold) for rec in existing]
    return {"sources": registry.versions(), "terms": list(groups.values()), "existing_curies": checked}


UNIT_PATTERN = re.compile(r"^(unit|UO):\S+$")


def fix_units(obj: Any) -> int:
    """Move any `unit` value the schema would reject into `unit_text`. Returns count moved."""
    moved = 0
    if isinstance(obj, dict):
        value = obj.get("unit")
        if isinstance(value, str) and not UNIT_PATTERN.match(value):
            if not obj.get("unit_text"):
                obj["unit_text"] = value
            del obj["unit"]
            moved += 1
        for v in obj.values():
            moved += fix_units(v)
    elif isinstance(obj, list):
        for v in obj:
            moved += fix_units(v)
    return moved


def apply_groundings(doc: Any, report: dict, selections: dict[str, str | None] | None = None) -> Any:
    """Copy of doc with resolved CURIEs (and LLM selections, keyed by term key) written in.
    Unmatched units are moved to unit_text so the graph validates."""
    selections = selections or {}
    grounded = copy.deepcopy(doc)
    for g in report["terms"]:
        curie = g["selected"] if g["status"] == "resolved" else selections.get(g.get("key") or term_key(g))
        if not curie:
            continue
        for loc in g["locations"]:
            get_at(grounded, loc["path"])[loc["field"]] = curie
    fix_units(grounded)
    return grounded


def summarise(report: dict) -> str:
    counts: dict[str, int] = defaultdict(int)
    for g in report["terms"]:
        counts[g["status"]] += 1
    existing: dict[str, int] = defaultdict(int)
    for c in report["existing_curies"]:
        existing[c.get("status", "").split(" ", 1)[0]] += 1
    return ("Summary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            + "; existing CURIEs: " + (", ".join(f"{k}={v}" for k, v in sorted(existing.items())) or "none"))


def load_doc(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) if path.endswith((".yaml", ".yml")) else json.load(fh)


def dump_doc(doc: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        if path.endswith((".yaml", ".yml")):
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
        else:
            json.dump(doc, fh, indent=2, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="LLM output: CAMO CausalGraph (JSON or YAML) or a list of nodes")
    ap.add_argument("--schema", help="causalmosaic.yaml, to take CURIE prefixes from the schema")
    ap.add_argument("--index-dir", help=f"directory with the built indexes (default {INDEX_DIR})")
    ap.add_argument("--report", default="grounding_report.json")
    ap.add_argument("--out", help="write a copy of the graph with resolved CURIEs filled in")
    ap.add_argument("--kinds", nargs="*", help="only ground these kinds (default: all configured)")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--fuzzy-cutoff", type=float, default=80.0)
    ap.add_argument("--taxon-online", action="store_true",
                    help="query NCBI E-utilities for taxa missing from the lexicon (answers are cached)")
    ap.add_argument("--skip-untyped", action="store_true", help="ignore entity_term without entity_type")
    ap.add_argument("--name-check-threshold", type=float, default=60.0,
                    help="flag existing CURIEs whose label/synonyms resemble the node name less than this")
    ap.add_argument("--rebuild-cache", action="store_true", help="rebuild cached OAK term tables")
    args = ap.parse_args()

    config = load_config()
    if args.index_dir:
        config["index_dir"] = args.index_dir
    prefix_map = CAMO_PREFIXES
    if args.schema:
        with open(args.schema, encoding="utf-8") as fh:
            prefix_map = {**CAMO_PREFIXES, **(yaml.safe_load(fh).get("prefixes") or {})}
    registry = Registry(config, Prefixes(prefix_map), args.rebuild_cache, args.taxon_online)

    doc = load_doc(args.input)
    report = ground_graph(doc, registry, args.kinds, args.top_k, args.fuzzy_cutoff,
                          args.skip_untyped, args.name_check_threshold)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    if args.out:
        dump_doc(apply_groundings(doc, report), args.out)
    print(summarise(report), file=sys.stderr)


if __name__ == "__main__":
    main()
