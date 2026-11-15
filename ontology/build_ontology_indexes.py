#!/usr/bin/env python3
"""
build_ontology_indexes.py - build the compact ontology indexes that ground_terms.py reads.

Run once on a development machine; commit the output directory (ontology_index/). The
pipeline then grounds terms with no OAK, no network and no multi-GB downloads.
See GROUNDING.md for the full workflow.

Inputs (obographs JSON, as published at the URLs in DOWNLOADS; --download fetches them):
  elmo-full.json  envo-full.json  go-full.json  pato-full.json  uberon.json   (raw_json/)
  ncbitaxon.json  (raw_json/; 2.4 GB; streamed with ijson, pruned to taxa named in the corpus)
  raw_json/ is <repo root>/raw_json (subfolders are searched too); --src-dir overrides it.
  PO publishes no JSON: it is read through OAK (sqlite:obo:po, a 4.6 MB download that OAK
  caches under ~/.data/oaklib). Needs oaklib (requirements-dev.txt).

Output (gzipped JSON, one file per source):
  ontology_index/<source>.json.gz
      {"source", "built", "inputs", "versions", "prefixes", "roots", "strip_suffixes",
       "strategy", "terms": {CURIE: {"l": label, "s": [[synonym, type], ...],
                                     "d": definition, "p": [parent labels]}}}
  ncbitaxon terms are {"l": label, "r": rank, "pa": parent CURIE, "s": [[name, type], ...]}
  ontology_index/manifest.json   counts and versions per source

Why not OAK's obograph adapter: on these files it is too slow (GO term details: >10 minutes
for 3,000 terms; PATO descendants(): 57 s) and crashes on nodes without "meta"
(obsoletes(), definition()). Reading the JSON directly takes seconds. OAK's sqlite
adapters are fast, so sources without JSON (PO) use those ("adapter" in SOURCES).

Usage
  python build_ontology_indexes.py --download --ncbitaxon     # everything, fetching what's missing
  python build_ontology_indexes.py                            # rebuild from files already here
  python build_ontology_indexes.py --only ncbitaxon                 # taxa only, from raw_json/
  python build_ontology_indexes.py --ncbitaxon /data/ncbitaxon.json --corpus corpus/
  python build_ontology_indexes.py --only pato elmo
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import sys
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

from ground_terms import CAMO_PREFIXES, Prefixes, norm_key, terms_from_oak

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "ontology_index"


# Defaults work whether this script sits at the repo root or one folder below it: the repo
# root is the folder that holds corpus/. Raw ontology files live in <repo root>/raw_json/
# (also where --download puts them); a checkout that keeps them loose at the root still works.
REPO_ROOT = ROOT if (ROOT / "corpus").exists() or not (ROOT.parent / "corpus").exists() else ROOT.parent
DEFAULT_CORPUS = REPO_ROOT / "corpus"
RAW_DIR = REPO_ROOT / "raw_json"
DEFAULT_SRC_DIR = RAW_DIR if RAW_DIR.exists() or not (REPO_ROOT / "elmo-full.json").exists() else REPO_ROOT


def find_input(src_dir: Path, name: str) -> Path:
    """src_dir/name, else the first file of that name in a subfolder of src_dir (so
    raw_json/ncbitaxon/ncbitaxon.json is found too). If absent: src_dir/name, the place a
    download goes."""
    direct = src_dir / name
    if direct.exists() or not src_dir.is_dir():
        return direct
    return next(iter(sorted(src_dir.rglob(name))), direct)

# name -> how to build it. "files" are read in order; terms whose CAMO prefix is not in
# "prefixes" are dropped (the full files also carry imported RO, BFO, UBERON... terms).
SOURCES: dict[str, dict] = {
    "elmo": {"files": ["elmo-full.json"], "prefixes": ["elmo", "elmo_cas"],
             "strip_suffixes": ["process"]},
    "envo": {"files": ["envo-full.json"], "prefixes": ["ENVO"]},
    "go": {"files": ["go-full.json"], "prefixes": ["GO"],
           "roots": ["GO:0008150"]},                             # biological_process
    "pato": {"files": ["pato-full.json"], "prefixes": ["PATO"],
             "roots": ["PATO:0000001"]},                         # quality
    # the CHEBI terms imported into ENVO and PATO: environmental chemicals without full ChEBI
    "chebi": {"files": ["envo-full.json", "pato-full.json"], "prefixes": ["CHEBI"], "subset": True},
    # PO publishes no obographs JSON; OAK's semantic-sql build is small and fast
    "po": {"adapter": "sqlite:obo:po", "prefixes": ["PO"], "roots": ["PO:0009012"], "optional": True,
           "strip_suffixes": ["development stage", "stage"]},       # "seedling development stage"
    "uberon": {"files": ["uberon.json"], "prefixes": ["UBERON"], "roots": ["UBERON:0000105"],
               "strip_suffixes": ["stage"],
               "optional": True},
}

# Where --download fetches each input file from (checked 2026-11-14).
DOWNLOADS = {
    "elmo-full.json": "https://raw.githubusercontent.com/timalamenciak/elmo/main/elmo-full.json",
    "envo-full.json": "http://purl.obolibrary.org/obo/envo.json",
    "go-full.json": "http://purl.obolibrary.org/obo/go.json",
    "pato-full.json": "http://purl.obolibrary.org/obo/pato.json",
    "uberon.json": "http://purl.obolibrary.org/obo/uberon.json",
    "ncbitaxon.json": "http://purl.obolibrary.org/obo/ncbitaxon.json",
}


def download(name: str, dest: Path) -> None:
    """Fetch DOWNLOADS[name] to dest (via a .part file, so an interrupted download is redone)."""
    url = DOWNLOADS[name]
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    print(f"downloading {name} from {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "camo-grounding-build/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as fh:
        total, done, last = int(resp.headers.get("Content-Length") or 0), 0, 0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if done - last >= 200 << 20:
                last = done
                print(f"  {done / 1e9:.1f} / {total / 1e9:.1f} GB", file=sys.stderr)
    part.rename(dest)


def build_oak_source(name: str, spec: dict, px: Prefixes) -> dict | None:
    try:
        data = terms_from_oak(name, spec, px, rebuild=True)
    except ImportError:
        print(f"{name}: needs oaklib (pip install -r requirements-dev.txt) - skipping", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"{name}: OAK could not open {spec['adapter']} ({exc}) - skipping", file=sys.stderr)
        return None
    data.update({"roots": spec.get("roots", []), "strip_suffixes": spec.get("strip_suffixes", []),
                 "subset": spec.get("subset", False), "inputs": [spec["adapter"]]})
    for term in data["terms"].values():
        for key in ("s", "d", "p"):
            if not term.get(key):
                term.pop(key, None)
    return data


SYN_TYPES = {"hasExactSynonym": "exact_synonym", "hasRelatedSynonym": "related_synonym",
             "hasNarrowSynonym": "narrow_synonym", "hasBroadSynonym": "broad_synonym"}
ALT_LABEL_PREDS = ("IAO_0000118", "skos/core#altLabel")             # alternative label
SKIP_SYNONYM_TYPES = ("Japanese", "Spanish", "French", "German", "Chinese", "abbreviation")
CURIE_LIKE = re.compile(r"^[A-Za-z_]+:\S+$")
DEF_MAX = 200


def short(pred: str) -> str:
    return pred.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def graph_version(graph: dict) -> str:
    meta = graph.get("meta") or {}
    for bpv in meta.get("basicPropertyValues") or []:
        if "versionInfo" in bpv.get("pred", ""):
            return str(bpv.get("val"))
    return str(meta.get("version") or graph.get("id") or "")


def node_synonyms(meta: dict) -> list[list[str]]:
    out: list[list[str]] = []
    for syn in meta.get("synonyms") or []:
        val = (syn.get("val") or "").strip()
        stype = syn.get("synonymType") or ""
        if not val or CURIE_LIKE.match(val) or any(t in stype for t in SKIP_SYNONYM_TYPES):
            continue
        out.append([val, SYN_TYPES.get(short(syn.get("pred", "")), "related_synonym")])
    for bpv in meta.get("basicPropertyValues") or []:
        val = str(bpv.get("val") or "").strip()
        if val and any(p in bpv.get("pred", "") for p in ALT_LABEL_PREDS) and not CURIE_LIKE.match(val):
            out.append([val, "alt_label"])
    seen, uniq = set(), []
    for val, typ in out:
        if (val.lower(), typ) not in seen:
            seen.add((val.lower(), typ))
            uniq.append([val, typ])
    return uniq


def descendants(roots: list[str], children: dict[str, set[str]]) -> set[str]:
    found, queue = set(roots), deque(roots)
    while queue:
        for child in children.get(queue.popleft(), ()):
            if child not in found:
                found.add(child)
                queue.append(child)
    return found


def build_obograph_source(name: str, spec: dict, px: Prefixes, base: Path) -> dict | None:
    paths = [find_input(base, f) for f in spec["files"]]
    missing = [p for p in paths if not p.exists()]
    if missing:
        level = "skipping (optional)" if spec.get("optional") else "SKIPPING"
        print(f"{name}: {', '.join(map(str, missing))} not found - {level}", file=sys.stderr)
        return None
    allowed = set(spec["prefixes"])
    terms: dict[str, dict] = {}
    labels: dict[str, str] = {}
    parents: dict[str, list[str]] = defaultdict(list)
    children: dict[str, set[str]] = defaultdict(set)
    obsolete: set[str] = set()
    versions = []
    for path in paths:
        print(f"{name}: reading {path.name}", file=sys.stderr)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for graph in doc.get("graphs", []):
            versions.append(f"{path.name}: {graph_version(graph)}")
            for node in graph.get("nodes", []):
                if node.get("type") not in (None, "CLASS"):
                    continue
                curie = px.to_camo(node["id"])
                label = (node.get("lbl") or "").strip()
                if label:
                    labels.setdefault(curie, label)
                meta = node.get("meta") or {}
                if meta.get("deprecated") or label.lower().startswith("obsolete "):
                    obsolete.add(curie)
                    continue
                if px.prefix_of(curie) not in allowed or not label or curie in terms:
                    continue
                definition = ((meta.get("definition") or {}).get("val") or "").strip()
                if len(definition) > DEF_MAX:
                    definition = definition[:DEF_MAX - 3] + "..."
                terms[curie] = {"l": label, "s": node_synonyms(meta), "d": definition}
            for edge in graph.get("edges", []):
                if edge.get("pred") != "is_a":
                    continue
                sub, obj = px.to_camo(edge["sub"]), px.to_camo(edge["obj"])
                if obj not in parents[sub]:
                    parents[sub].append(obj)
                children[obj].add(sub)
    if spec.get("roots"):
        keep = descendants(spec["roots"], children)
        terms = {c: t for c, t in terms.items() if c in keep}
    for curie in obsolete:
        terms.pop(curie, None)
    for curie, term in terms.items():
        term["p"] = [labels[p] for p in parents.get(curie, []) if p in labels][:3]
        if not term["s"]:
            del term["s"]
        if not term["d"]:
            del term["d"]
    return {"source": name, "strategy": "lexical", "inputs": spec["files"], "versions": versions,
            "prefixes": spec["prefixes"], "roots": spec.get("roots", []),
            "strip_suffixes": spec.get("strip_suffixes", []), "subset": spec.get("subset", False),
            "terms": terms}


# ---------------------------------------------------------------------------
# NCBITaxon: stream the 2.2 GB obographs file, keep taxa named in the corpus
# ---------------------------------------------------------------------------

TAXON_SKIP_TYPES = ("authority", "misspelling", "acronym", "in_part", "includes")
MAX_NGRAM = 4


def corpus_ngrams(corpus_dir: Path) -> set[str]:
    grams: set[str] = set()
    for path in sorted(corpus_dir.glob("*.md")):
        tokens = norm_key(path.read_text(encoding="utf-8", errors="replace")).split()
        for n in range(1, MAX_NGRAM + 1):
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i:i + n])
                if len(gram) >= 3 and not gram[0].isdigit():
                    grams.add(gram)
    return grams


def ncbi_curie(iri: str) -> str:
    return "NCBITaxon:" + iri.rsplit("_", 1)[-1] if "NCBITaxon_" in iri else iri


def build_ncbitaxon(path: Path, corpus_dir: Path, extra_names: list[str]) -> dict:
    import ijson

    print(f"ncbitaxon: collecting corpus n-grams from {corpus_dir}", file=sys.stderr)
    grams = corpus_ngrams(corpus_dir) | {norm_key(n) for n in extra_names}
    print(f"ncbitaxon: {len(grams):,} distinct corpus n-grams", file=sys.stderr)

    label_of: dict[int, str] = {}
    rank_of: dict[int, str] = {}
    matched: dict[int, list[list[str]]] = {}
    ranks: dict[str, str] = {}
    print(f"ncbitaxon: pass 1 (nodes) over {path}", file=sys.stderr)
    with open(path, "rb") as fh:
        for i, node in enumerate(ijson.items(fh, "graphs.item.nodes.item")):
            iri = node.get("id", "")
            if "NCBITaxon_" not in iri:
                continue
            try:
                tid = int(iri.rsplit("_", 1)[-1])
            except ValueError:
                continue
            label = node.get("lbl") or ""
            label_of[tid] = label
            meta = node.get("meta") or {}
            for bpv in meta.get("basicPropertyValues") or []:
                if "has_rank" in bpv.get("pred", ""):
                    rank = str(bpv.get("val", "")).split("NCBITaxon_", 1)[-1]
                    rank_of[tid] = ranks.setdefault(rank, rank)
            names = [[label, "label"]] if label else []
            for syn in meta.get("synonyms") or []:
                stype = syn.get("synonymType") or ""
                val = (syn.get("val") or "").strip()
                if val and not any(t in stype for t in TAXON_SKIP_TYPES):
                    kind = SYN_TYPES.get(short(syn.get("pred", "")), "related_synonym")
                    if "common_name" in stype and kind == "related_synonym":
                        kind = "common_name"
                    names.append([val, kind])
            hits = [n for n in names if norm_key(n[0]) in grams]
            if hits:
                matched[tid] = names
            if i and i % 500_000 == 0:
                print(f"  {i:,} nodes, {len(matched):,} matched", file=sys.stderr)

    print("ncbitaxon: pass 2 (is_a edges)", file=sys.stderr)
    parent_of: dict[int, int] = {}
    with open(path, "rb") as fh:
        for edge in ijson.items(fh, "graphs.item.edges.item"):
            if edge.get("pred") == "is_a":
                try:
                    parent_of[int(edge["sub"].rsplit("_", 1)[-1])] = int(edge["obj"].rsplit("_", 1)[-1])
                except (KeyError, ValueError):
                    continue

    keep: set[int] = set()
    for tid in matched:
        node, steps = tid, 0
        while node and node not in keep and steps < 80:
            keep.add(node)
            node, steps = parent_of.get(node), steps + 1
    keep.discard(1)                                                        # "root"
    terms = {}
    for tid in sorted(keep):
        term = {"l": label_of.get(tid, ""), "r": rank_of.get(tid, "")}
        if parent_of.get(tid) and parent_of[tid] != 1:
            term["pa"] = f"NCBITaxon:{parent_of[tid]}"
        names = [n for n in matched.get(tid, []) if n[1] != "label"]
        if names:
            term["s"] = names
        terms[f"NCBITaxon:{tid}"] = term
    print(f"ncbitaxon: {len(matched):,} taxa matched, {len(terms):,} kept with ancestors",
          file=sys.stderr)
    return {"source": "ncbitaxon", "strategy": "taxon", "inputs": [path.name],
            "versions": [f"{path.name}"], "prefixes": ["NCBITaxon"], "roots": [],
            "strip_suffixes": [], "subset": True, "corpus": str(corpus_dir), "terms": terms}


def write_index(data: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    data["built"] = dt.date.today().isoformat()
    path = out_dir / f"{data['source']}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    info = {"file": path.name, "terms": len(data["terms"]), "bytes": path.stat().st_size,
            "versions": data.get("versions", []), "built": data["built"]}
    print(f"wrote {path} ({info['terms']:,} terms, {info['bytes'] / 1e6:.2f} MB)", file=sys.stderr)
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", default=str(DEFAULT_SRC_DIR),
                    help=f"directory holding the raw ontology files, searched including subfolders "
                         f"(default {DEFAULT_SRC_DIR})")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--ncbitaxon", nargs="?", const="ncbitaxon.json",
                    help="build the taxon lexicon from this file (without the option: built anyway when "
                         "ncbitaxon*.json is in --src-dir)")
    ap.add_argument("--download", action="store_true",
                    help="download any missing input file first (NCBITaxon only with --ncbitaxon: 2.4 GB)")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS),
                    help=f"folder of *.md articles used to prune NCBITaxon (default {DEFAULT_CORPUS})")
    ap.add_argument("--extra-taxa", nargs="*", default=[],
                    help="extra taxon names to keep even if not in the corpus (e.g. from the example)")
    ap.add_argument("--only", nargs="*", help="build only these sources")
    args = ap.parse_args()

    px = Prefixes(CAMO_PREFIXES)
    out_dir = Path(args.out_dir)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    src_dir = Path(args.src_dir)
    want_ncbi = not args.only or "ncbitaxon" in args.only
    ncbi_path = None
    if args.ncbitaxon:
        ncbi_path = Path(args.ncbitaxon)
        ncbi_path = ncbi_path if ncbi_path.is_absolute() or ncbi_path.exists() else find_input(src_dir, str(ncbi_path))
        if not ncbi_path.exists() and args.ncbitaxon == "ncbitaxon.json" and src_dir.is_dir():
            # bare --ncbitaxon: use whatever ncbitaxon*.json is already there before downloading one
            ncbi_path = next(iter(sorted(src_dir.rglob("ncbitaxon*.json"))), ncbi_path)
    elif want_ncbi:
        # no --ncbitaxon: build from the raw file anyway when it is there (raw_json/ncbitaxon*.json)
        found = sorted(src_dir.rglob("ncbitaxon*.json")) if src_dir.is_dir() else []
        ncbi_path = found[0] if found else None
        if ncbi_path is None and args.only:
            sys.exit(f"--only ncbitaxon: no ncbitaxon*.json in {src_dir} (or its subfolders). Put the file "
                     f"there, pass --ncbitaxon /path/to/ncbitaxon.json, or add --ncbitaxon --download")
    if want_ncbi and ncbi_path is not None and not any(Path(args.corpus).glob("*.md")):
        # checked before the 2.4 GB download/stream: no articles would give an empty lexicon
        sys.exit(f"no *.md articles in {args.corpus}; pass --corpus <folder with the articles>")
    if args.download:
        wanted = {f for n, spec in SOURCES.items() if not args.only or n in args.only
                  for f in spec.get("files", [])}
        for fname in sorted(wanted):
            if fname in DOWNLOADS and not find_input(src_dir, fname).exists():
                download(fname, src_dir / fname)
        if ncbi_path is not None and not ncbi_path.exists():
            download("ncbitaxon.json", ncbi_path)
    for name, spec in SOURCES.items():
        if args.only and name not in args.only:
            continue
        if "adapter" in spec:
            data = build_oak_source(name, spec, px)
        else:
            data = build_obograph_source(name, spec, px, src_dir)
        if data:
            manifest[name] = write_index(data, out_dir)
    if want_ncbi and ncbi_path is not None:
        if not ncbi_path.exists():
            sys.exit(f"ncbitaxon: {ncbi_path} not found (add --download to fetch it, 2.4 GB)")
        data = build_ncbitaxon(ncbi_path, Path(args.corpus), args.extra_taxa)
        manifest["ncbitaxon"] = write_index(data, out_dir)
    elif want_ncbi:
        print(f"ncbitaxon: no ncbitaxon*.json in {src_dir} - taxon index NOT built "
              f"(existing one, if any, left as is); taxa will stay free text", file=sys.stderr)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
