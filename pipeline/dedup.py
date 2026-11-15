"""Merge step: one node per distinct node content across the whole graph (no duplicate nodes).

Each paper's nodes get paper-scoped IDs (`node:{slug}_{hash of the parse key}`), so the same entity is a separate node in
every paper, and inside one paper two parse keys can end up as the same node after later rewrites (null result drops
'=', the guard's 'unchanged object on null result' repair, grounding and ontology rewrites).  This step gives every
distinct node content ONE node with a deterministic ID and points the edges at it.

- Identity = every node field except id, source_spans, variable_key, embedding_*, annotator, compared after light
  normalisation (free text: NFKC, lowercase, whitespace collapsed; CURIEs as they are; applied_to as a sorted list).
  The state_or_change_qualifier is part of the identity: "Increased X" and "Decreased X" stay two nodes.
- The name is part of the identity too (exact, case kept): the scorer reads a node's entity from its name when
  entity_term is a CURIE, so a merge must never rename a paper's node.  Same content under another name (e.g. two
  words grounded to one CURIE) is reported, not merged.
- Exact matches only (under-merge rather than over-merge).  Near misses are reported, not merged (near_duplicate_rows).
- Edges are never merged: every edge keeps its id, source_document, sentence and spans.  Only node references change.
- The schema closes CausalNode, so the source node IDs and documents live in sidecar rows (node_map); each span on a
  shared node carries its paper in sentence_id ('{slug}:s{n}', set by expand.py).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .guard import _CURIE, same_sentence_key

IGNORED_FIELDS = frozenset({"id", "name", "source_spans", "variable_key", "embedding_text", "embedding_vector", "annotator"})
MAX_SPANS_PER_DOC = 6                     # the per-paper cap expand.py applies to a node's spans; kept per paper here


def _norm_text(s: str) -> str:
    if _CURIE.match(s) or s.startswith(("http://", "https://")):
        return s
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()


def _norm(v):
    if isinstance(v, str):
        return _norm_text(v)
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in sorted(v.items()) if x is not None}
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def content_key(node: dict, with_name: bool = True) -> str:
    """The node's identity as a canonical JSON string (with_name=False: the content alone, for the near-duplicate report)."""
    key = {k: _norm(v) for k, v in node.items() if k not in IGNORED_FIELDS and v is not None}
    if with_name:
        key["name"] = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(node.get("name", "")))).strip()
    if isinstance(key.get("applied_to"), list):
        key["applied_to"] = sorted(key["applied_to"], key=lambda a: json.dumps(a, sort_keys=True, ensure_ascii=False))
    return json.dumps(key, sort_keys=True, ensure_ascii=False)


def canonical_id(key: str) -> str:
    return "node:v_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def variable_key(node: dict) -> str:
    """entity_term + measured_attribute + applied_to (the schema's definition); the qualifier is not part of it."""
    applied = ",".join(sorted(str(a.get("entity_term", "")) for a in node.get("applied_to") or []))
    return f"{node.get('entity_term', '')}|{node.get('measured_attribute') or ''}|{applied}"


def _span_key(sp: dict) -> tuple:
    return (sp.get("text"), sp.get("start_char"), sp.get("end_char"), sp.get("sentence_id"))


def _remap(e: dict, ref: Dict[str, str]) -> dict:
    """A copy of edge `e` with every node reference mapped through `ref` (ids missing from `ref` are left alone)."""
    e = dict(e)
    for k in ("subject", "object"):
        if e.get(k) in ref:
            e[k] = ref[e[k]]
    for block, field in (("mediation", "mediator_node_ids"), ("moderation", "moderator_node_ids")):
        b = e.get(block)
        if isinstance(b, dict) and b.get(field):
            b = dict(b)
            b[field] = list(dict.fromkeys(ref.get(i, i) for i in b[field]))
            e[block] = b
    if isinstance(e.get("comparator"), list):
        comps = []
        for c in e["comparator"]:
            if isinstance(c, dict) and c.get("comparator_node_id") in ref:
                c = dict(c, comparator_node_id=ref[c["comparator_node_id"]])
            comps.append(c)
        e["comparator"] = comps
    return e


def dedupe(docs: Sequence[Tuple[str, Dict[str, dict], List[dict]]]) -> Tuple[List[dict], List[dict], List[dict], Counter]:
    """docs = [(slug, nodes by id, edges)] in output order.  Returns (nodes, edges, node_map rows, stats).

    Canonical IDs depend only on node content, so they do not change with the paper order; span order is decided over
    the papers sorted by slug, so it does not either."""
    stats: Counter = Counter()
    key_of: Dict[Tuple[str, str], str] = {}                 # (slug, source node id) -> content key
    members: Dict[str, List[Tuple[str, dict]]] = defaultdict(list)
    order: List[str] = []                                    # content keys in order of first appearance (output order)
    for slug, nodes, _ in docs:
        for nid, n in nodes.items():
            k = content_key(n)
            key_of[(slug, nid)] = k
            if k not in members:
                order.append(k)
            members[k].append((slug, n))
    out_nodes: List[dict] = []
    for k in order:
        mem = sorted(members[k], key=lambda m: m[0])       # sorted() is stable: within a paper, first-made node first
        node = dict(mem[0][1])
        node["id"] = canonical_id(k)
        spans: List[dict] = []
        seen: set = set()
        per_doc: Counter = Counter()
        for slug, n in mem:
            for sp in n.get("source_spans") or []:
                sk = _span_key(sp)
                if sk in seen or per_doc[slug] >= MAX_SPANS_PER_DOC:
                    continue
                seen.add(sk)
                per_doc[slug] += 1
                spans.append(sp)
        node.pop("source_spans", None)
        if spans:
            node["source_spans"] = spans
        node["variable_key"] = variable_key(node)
        out_nodes.append(node)
        docs_in = {s for s, _ in mem}
        if len(mem) > 1:
            stats["node groups merged"] += 1
            stats["nodes merged away"] += len(mem) - 1
            if len(docs_in) > 1:
                stats["node groups shared by several papers"] += 1
            if len(docs_in) < len(mem):
                stats["node groups with repeats inside one paper"] += 1

    node_map: List[dict] = []
    out_edges: List[dict] = []
    for slug, nodes, edges in docs:
        ref = {nid: canonical_id(key_of[(slug, nid)]) for nid in nodes}
        size = {nid: len(members[key_of[(slug, nid)]]) for nid in nodes}
        for nid in nodes:
            node_map.append({"source_node_id": nid, "document_id": slug, "canonical_node_id": ref[nid],
                             "method": "exact_content" if size[nid] > 1 else "singleton"})
        seen_claims: set = set()
        for e in edges:
            e2 = _remap(e, ref)
            claim = (e2.get("source_document"),) + same_sentence_key(e2)
            if claim in seen_claims:                           # two node IDs for one content made this claim look new
                stats["dropped edge: same claim, same sentence (after node merge)"] += 1
                continue
            seen_claims.add(claim)
            out_edges.append(e2)
    stats["nodes in"] = sum(len(n) for _, n, _ in docs)
    stats["nodes out"] = len(out_nodes)
    return out_nodes, out_edges, node_map, stats


# ----------------------------------------------------------------------------------------------- reports
def _loose(s: Optional[str]) -> str:
    """Looser than content_key: punctuation dropped, a trailing plural 's' dropped from each word."""
    words = re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", str(s or "")).lower()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


def near_duplicate_rows(nodes: Iterable[dict]) -> List[dict]:
    """Pairs of nodes that are NOT merged but probably should be, after review:
    - same content, different name (e.g. two words grounded to one CURIE): merging would rename a paper's node;
    - free-text terms that match once punctuation and a plural 's' are ignored (same type, qualifier, life stage,
      applied_to; entity_term + measured_attribute compared loosely)."""
    nodes = list(nodes)
    rows: List[dict] = []
    seen: set = set()

    def pairs(groups, reason):
        for g in groups.values():
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    if (g[i]["id"], g[j]["id"]) not in seen:
                        seen.add((g[i]["id"], g[j]["id"]))
                        rows.append({"node_a": g[i]["id"], "name_a": g[i]["name"], "node_b": g[j]["id"],
                                     "name_b": g[j]["name"], "reason_not_merged": reason})

    same: Dict[str, List[dict]] = defaultdict(list)
    for n in nodes:
        same[content_key(n, with_name=False)].append(n)
    pairs(same, "same content, different name; merging would rename a paper's node")
    loose: Dict[tuple, List[dict]] = defaultdict(list)
    for n in nodes:
        term = str(n.get("entity_term", ""))
        if _CURIE.match(term):
            continue
        applied = tuple(sorted(_loose(a.get("entity_term")) for a in n.get("applied_to") or []))
        loose[(n.get("entity_type"), n.get("state_or_change_qualifier"), n.get("life_stage"), applied,
               _loose(term), _loose(n.get("measured_attribute")))].append(n)
    pairs(loose, "string variant (punctuation or plural); exact-content merge only")
    return rows


def write_reports(out_dir, nodes: Sequence[dict], node_map: Sequence[dict]) -> None:
    """node_map.csv (every source node id -> its canonical node), merged_nodes.csv (per node: all source node ids and
    documents, '|'-joined), near_duplicates.csv (not merged, for review)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "node_map.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_node_id", "document_id", "canonical_node_id", "method"])
        w.writeheader()
        w.writerows(node_map)
    src: Dict[str, List[str]] = defaultdict(list)
    docs: Dict[str, List[str]] = defaultdict(list)
    for r in node_map:
        src[r["canonical_node_id"]].append(r["source_node_id"])
        if r["document_id"] not in docs[r["canonical_node_id"]]:
            docs[r["canonical_node_id"]].append(r["document_id"])
    with open(out / "merged_nodes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["canonical_node_id", "name", "entity_type", "variable_key", "n_source_nodes", "n_documents",
                    "source_node_ids", "source_document_ids"])
        for n in nodes:
            w.writerow([n["id"], n["name"], n.get("entity_type", ""), n.get("variable_key", ""), len(src[n["id"]]),
                        len(docs[n["id"]]), "|".join(src[n["id"]]), "|".join(docs[n["id"]])])
    rows = near_duplicate_rows(nodes)
    with open(out / "near_duplicates.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["node_a", "name_a", "node_b", "name_b", "reason_not_merged"])
        w.writeheader()
        w.writerows(rows)
