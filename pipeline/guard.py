"""Stage 5: per-item validation and repair, integrity checks, and the merge into one CausalGraph."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import fastjsonschema
import yaml

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_JSON = ROOT / "data" / "camo.schema.json"
SCHEMA_YAML = ROOT / "schema" / "causalmosaic.yaml"
SCHEMA_VERSION = "0.10.0"

_CORRELATION_STAT = re.compile(r"(?<![A-Za-z])(?:R2?|r2?|ρ|τ|rho|tau)(?![A-Za-z])")
_CURIE = re.compile(r"^([A-Za-z][A-Za-z0-9_.\-]*):[^\s/]\S*$")


@lru_cache(maxsize=1)
def validator():
    return fastjsonschema.compile(json.loads(SCHEMA_JSON.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def declared_prefixes() -> set:
    return set((yaml.safe_load(SCHEMA_YAML.read_text(encoding="utf-8")).get("prefixes") or {}).keys())


def validate_graph(graph: dict) -> Optional[fastjsonschema.JsonSchemaValueException]:
    try:
        validator()(graph)
        return None
    except fastjsonschema.JsonSchemaValueException as e:
        return e


def wrapper_graph(nodes: Sequence[dict], edges: Sequence[dict]) -> dict:
    return {"graph_id": "wrapper", "schema_version": SCHEMA_VERSION, "provenance": {}, "nodes": list(nodes), "edges": list(edges)}


# ----------------------------------------------------------------------------------------------- repairs
def repair_edge(edge: dict) -> List[str]:
    """Rule-based fixes for known-bad combinations.  Returns the names of the repairs applied."""
    done: List[str] = []
    p, lang = edge.get("predicate"), edge.get("causal_language")
    if p == "causes" and lang == "associational":
        edge["predicate"] = "associated_with"
        done.append("causes+associational->associated_with")
    elif p in ("associated_with", "correlated_with", "precedes") and lang in ("direct_causal", "uncertain_causal"):
        edge["predicate"] = "contributes_to"
        done.append(f"{p}+{lang}->contributes_to")
    if edge.get("predicate") == "correlated_with" and not _CORRELATION_STAT.search(edge.get("original_sentence") or ""):
        edge["predicate"] = "associated_with"
        done.append("correlated_with without statistic->associated_with")
    return done


def _path(exc) -> List:
    """'data.edges[0].strength.significance' -> ['edges', 0, 'strength', 'significance']"""
    toks: List = []
    for m in re.finditer(r"\.([A-Za-z_][\w\-]*)|\[(\d+)\]", exc.name or ""):
        toks.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
    return toks


def _label(path: Sequence) -> str:
    """['edges', 0, 'strength', 'significance'] -> 'strength.significance';  ['nodes', 2, 'life_stage'] -> 'node.life_stage'"""
    names = [str(x) for x in path if not isinstance(x, int)]
    if names and names[0] == "edges":
        names = names[1:]
    elif names and names[0] == "nodes":
        names = ["node"] + names[1:]
    return ".".join(names)


def _get(g: object, path: Sequence):
    for k in path:
        g = g[k]
    return g


def _error_under(g: dict, name: str) -> bool:
    """Does validation still report an error at (or below) `name`?  Errors elsewhere do not count."""
    exc = validate_graph(g)
    return exc is not None and (exc.name or "").startswith(name)


def _repair_value(g: dict, path: List, name: str) -> str:
    """Fix the value at `path` with the smallest loss: empty it, then put fields (or list items) back one at a time and
    keep only those that do not bring the error back.  Falls back to deleting the whole value."""
    parent = _get(g, path[:-1])
    key = path[-1]
    value = parent[key]
    if isinstance(value, dict) and len(value) > 1:
        orig = dict(value)
        value.clear()
        if not _error_under(g, name):
            dropped = []
            for k, v in orig.items():
                value[k] = v
                if _error_under(g, name):
                    del value[k]
                    dropped.append(k)
            if dropped:
                return "+".join(f"{_label(path)}.{k}" for k in dropped)
        value.clear()
        value.update(orig)
    elif isinstance(value, list) and len(value) > 1:
        orig = list(value)
        value.clear()
        if not _error_under(g, name):
            dropped = 0
            for item in orig:
                value.append(item)
                if _error_under(g, name):
                    value.pop()
                    dropped += 1
            if dropped:
                return f"{_label(path)}[{dropped} item(s)]"
        value[:] = orig
    del parent[key]
    return _label(path)


def validate_edge(edge: dict, nodes: Dict[str, dict]) -> Tuple[Optional[dict], Dict[str, dict], List[str]]:
    """Validate one edge together with the nodes it uses.  Optional fields that break validation are dropped (as little as
    possible: one field at a time); if a required field is the problem the edge is dropped.
    Returns (edge | None, cleaned nodes, notes)."""
    ids = [edge.get("subject"), edge.get("object")] + list((edge.get("mediation") or {}).get("mediator_node_ids") or [])
    used = {i: copy.deepcopy(nodes[i]) for i in ids if i in nodes}
    g = wrapper_graph(list(used.values()), [copy.deepcopy(edge)])
    notes: List[str] = []
    for _ in range(40):
        exc = validate_graph(g)
        if exc is None:
            return g["edges"][0], {n["id"]: n for n in g["nodes"]}, notes
        path = _path(exc)
        if exc.rule == "required" or len(path) < 3:               # a required field is the problem, or the item itself is wrong
            return None, used, notes + [f"unrepairable: {exc.message[:140]}"]
        try:
            notes.append("dropped " + _repair_value(g, path, exc.name))
        except (KeyError, IndexError, TypeError):
            return None, used, notes + [f"unrepairable: {exc.message[:140]}"]
    return None, used, notes + ["gave up after 40 repairs"]


# ----------------------------------------------------------------------------------------------- per paper
def guard_paper(slug: str, nodes: Dict[str, dict], edges: List[dict], features=None) -> Tuple[Dict[str, dict], List[dict], Counter]:
    """Repair + validate every edge of one paper; return the surviving nodes and edges."""
    stats: Counter = Counter()
    keep_edges: List[dict] = []
    clean_nodes = dict(nodes)
    for e in edges:
        for r in repair_edge(e):
            stats["repair: " + r] += 1
        if features is not None and features.double_negative:          # --double-negative
            from .features import repair_double_negative
            r = repair_double_negative(e, clean_nodes)
            if r:
                stats["repair: " + r] += 1
        if e.get("subject") not in clean_nodes or e.get("object") not in clean_nodes:
            stats["dropped edge: dangling"] += 1
            continue
        ok, cleaned, notes = validate_edge(e, clean_nodes)
        for n in notes:
            stats[("field " + n) if n.startswith("dropped") else ("edge " + n.split(":")[0])] += 1
        if ok is None:
            stats["dropped edge: schema"] += 1
            log.debug("%s: edge %s dropped (%s)", slug, e.get("id"), notes[-1] if notes else "")
            continue
        clean_nodes.update(cleaned)
        keep_edges.append(ok)
    clean_nodes, keep_edges = integrity(slug, clean_nodes, keep_edges, {slug}, stats)
    return clean_nodes, keep_edges, stats


def _fix_curies(node: dict, stats: Counter) -> None:
    pre = declared_prefixes()
    m = _CURIE.match(str(node.get("entity_term", "")))
    if m and m.group(1) not in pre and not str(node["entity_term"]).startswith(("http://", "https://")):
        node["entity_term"] = node.get("name") or str(node["entity_term"]).split(":", 1)[1]
        stats["repair: undeclared prefix in entity_term"] += 1
    ma = node.get("measured_attribute")
    m = _CURIE.match(str(ma or ""))
    if m and m.group(1) not in pre and not str(ma).startswith(("http://", "https://")):
        del node["measured_attribute"]
        stats["repair: undeclared prefix in measured_attribute"] += 1
    for a in node.get("applied_to") or []:
        m = _CURIE.match(str(a.get("entity_term", "")))
        if m and m.group(1) not in pre and not str(a["entity_term"]).startswith(("http://", "https://")):
            a["entity_term"] = str(a["entity_term"]).split(":", 1)[1]
            stats["repair: undeclared prefix in applied_to"] += 1


def same_sentence_key(e: dict) -> tuple:
    """One claim = subject, predicate, object, null flag, mediators, cited sentence(s).  The same claim twice from the same
    sentence is a model repeat (the first is kept); the same claim from different sentences is kept (the gold does that)."""
    spans = tuple(sorted((s.get("start_char"), s.get("end_char"), s.get("text")) for s in e.get("source_spans") or []))
    mids = tuple((e.get("mediation") or {}).get("mediator_node_ids") or [])
    return (e.get("subject"), e.get("predicate"), e.get("object"), bool(e.get("negated")), mids,
            spans or e.get("original_sentence"))


def integrity(slug: str, nodes: Dict[str, dict], edges: List[dict], doc_ids: set, stats: Counter) -> Tuple[Dict[str, dict], List[dict]]:
    out: List[dict] = []
    seen: set = set()
    seen_claims: set = set()
    for e in edges:
        mids = (e.get("mediation") or {}).get("mediator_node_ids") or []
        if e.get("subject") not in nodes or e.get("object") not in nodes or any(m not in nodes for m in mids):
            stats["dropped edge: dangling"] += 1
            continue
        if e.get("source_document") not in doc_ids:
            stats["dropped edge: bad source_document"] += 1
            continue
        if e["id"] in seen:
            stats["dropped edge: duplicate id"] += 1
            continue
        seen.add(e["id"])
        claim = same_sentence_key(e)
        if claim in seen_claims:
            stats["dropped edge: same claim, same sentence"] += 1
            continue
        seen_claims.add(claim)
        neg, lang = bool(e.get("negated")), e.get("causal_language")
        if neg and lang != "no_relationship":
            e["causal_language"] = "no_relationship"
            stats["repair: negated -> no_relationship"] += 1
        elif lang == "no_relationship" and not neg:
            e["negated"] = True
            stats["repair: no_relationship -> negated"] += 1
        if e.get("negated"):
            o = nodes[e["object"]]
            if o.get("state_or_change_qualifier") == "unchanged":
                o = dict(o)
                del o["state_or_change_qualifier"]
                nodes[e["object"]] = o
                stats["repair: unchanged object on null result"] += 1
        out.append(e)
    for n in nodes.values():
        _fix_curies(n, stats)
    used = {e["subject"] for e in out} | {e["object"] for e in out} | {m for e in out for m in (e.get("mediation") or {}).get("mediator_node_ids") or []}
    kept = {i: n for i, n in nodes.items() if i in used}
    stats["dropped nodes: unused"] += len(nodes) - len(kept)
    return kept, out


# ----------------------------------------------------------------------------------------------- merge
def source_document(row: Dict[str, str], doi: Optional[str] = None) -> dict:
    """`doi` (from the index or the markdown fallback, see pipeline.doi) overrides the raw index.csv cell."""
    d: dict = {"document_id": row["slug"]}
    doi = (doi if doi is not None else row.get("doi", "")).strip()
    if doi:
        d["doi"] = doi
    if row.get("title", "").strip():
        d["title"] = row["title"].strip()
    authors = [a.strip() for a in (row.get("authors") or "").split(";") if a.strip()]
    if authors:
        d["authors"] = authors
    try:
        d["year"] = int(str(row.get("year", "")).strip())
    except ValueError:
        pass
    if row.get("journal", "").strip():
        d["journal"] = row["journal"].strip()
    return d


def merge(index_rows: Sequence[Dict[str, str]], per_doc: Dict[str, Tuple[Dict[str, dict], List[dict]]],
          created: Optional[str] = None, dois: Optional[Dict[str, str]] = None, study: Optional[Dict[str, dict]] = None) -> dict:
    """One CausalGraph.  Every article in index.csv gets a source_documents entry, whether or not extraction worked."""
    nodes: List[dict] = []
    edges: List[dict] = []
    for row in index_rows:
        n, e = per_doc.get(row["slug"], ({}, []))
        nodes.extend(n.values())
        edges.extend(e)
    if not edges:
        raise RuntimeError("no edges at all: extraction failed for every document, refusing to write an invalid graph")
    return {
        "graph_id": "evidencejam2026_lane1", "schema_version": SCHEMA_VERSION,
        "provenance": {"causal_mosaic_version": SCHEMA_VERSION,
                       "created": created or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "source_corpus": "Evidence Jam 2026 Lane 1 corpus (ecological restoration articles)"},
        "source_documents": [dict(source_document(r, (dois or {}).get(r["slug"])), **(study or {}).get(r["slug"], {}))
                             for r in index_rows],
        "nodes": nodes, "edges": edges,
    }


def final_integrity(graph: dict) -> List[str]:
    """Whole-graph checks the per-edge validation cannot see."""
    problems: List[str] = []
    ids = Counter(n["id"] for n in graph["nodes"])
    problems += [f"duplicate node id {k}" for k, v in ids.items() if v > 1]
    eids = Counter(e["id"] for e in graph["edges"])
    problems += [f"duplicate edge id {k}" for k, v in eids.items() if v > 1]
    docs = {d["document_id"] for d in graph["source_documents"]}
    for e in graph["edges"]:
        if e["subject"] not in ids or e["object"] not in ids:
            problems.append(f"edge {e['id']}: dangling endpoint")
        if e.get("source_document") not in docs:
            problems.append(f"edge {e['id']}: source_document {e.get('source_document')!r} not in source_documents")
        for m in (e.get("mediation") or {}).get("mediator_node_ids") or []:
            if m not in ids:
                problems.append(f"edge {e['id']}: dangling mediator {m}")
    return problems
