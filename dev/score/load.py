"""Load gold / predicted graphs (wrapper or plain CausalGraph) into flat, normalised edge records."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

import yaml

from .normalise import NodeSig, node_sig, taxon_ids_in


@dataclass(frozen=True)
class EdgeRec:
    doc: str
    edge_id: str
    finding_id: Optional[str]
    sentence: Optional[str]
    subj: NodeSig
    obj: NodeSig
    predicate: Optional[str]
    causal_language: Optional[str]
    null: bool
    accounts: FrozenSet[str]
    significance: Optional[str]
    p_value: Optional[float]
    dose_level: Tuple[str, ...]
    has_dose: bool
    seasons: FrozenSet[str]
    mediators: Tuple[NodeSig, ...]
    spans: Tuple[Tuple[Optional[int], Optional[int], str], ...]
    finding_ids: Tuple[str, ...] = ()
    merged_ids: Tuple[str, ...] = ()
    sentences: Tuple[str, ...] = ()


@dataclass
class LoadedGraphs:
    """Everything read from one file."""
    path: str
    fmt: str                                  # 'wrapper' | 'graph'
    edges_by_doc: Dict[str, List[EdgeRec]] = field(default_factory=dict)
    findings_by_doc: Dict[str, List[str]] = field(default_factory=dict)     # wrapper only
    raw_graphs: List[dict] = field(default_factory=list)                    # for validity checks


def is_null(edge: dict) -> bool:
    """A null result is `negated: true` OR `causal_language == no_relationship` (the Murphy gold mixes both)."""
    return bool(edge.get("negated")) or edge.get("causal_language") == "no_relationship"


def _as_tuple(v) -> Tuple[str, ...]:
    if v is None:
        return ()
    if isinstance(v, (list, tuple, set)):
        return tuple(str(x) for x in v)
    return (str(v),)


def edge_record(edge: dict, nodes: Dict[str, dict], doc: str, finding_id: Optional[str] = None,
                wrapper_sentence: Optional[str] = None) -> Optional[EdgeRec]:
    s, o = nodes.get(edge.get("subject")), nodes.get(edge.get("object"))
    if s is None or o is None:
        return None                                              # dangling: reported by the validity checks
    null = is_null(edge)
    dose = edge.get("dose") or {}
    counted = taxon_ids_in((dose.get("counted_entity") or {}).get("entity_term")) if isinstance(dose, dict) else frozenset()
    # the dose's counted entity names the taxon of an intervention node ("5 ramets/m2 of S. canadensis")
    subj = node_sig(s, False, counted)
    obj = node_sig(o, null)
    strength = edge.get("strength") or {}
    te = edge.get("temporal_extent") or {}
    mediators = []
    for mid in (edge.get("mediation") or {}).get("mediator_node_ids") or []:
        if mid in nodes:
            mediators.append(node_sig(nodes[mid]))
    spans = tuple((sp.get("start_char"), sp.get("end_char"), sp.get("text", "")) for sp in edge.get("source_spans") or []
                  if isinstance(sp, dict))
    sentence = edge.get("original_sentence") or wrapper_sentence
    p = strength.get("p_value")
    try:
        p = float(p) if p is not None else None
    except (TypeError, ValueError):
        p = None
    return EdgeRec(doc=doc, edge_id=str(edge.get("id")), finding_id=finding_id, sentence=sentence, subj=subj, obj=obj,
                   predicate=edge.get("predicate"), causal_language=edge.get("causal_language"), null=null,
                   accounts=frozenset(edge.get("philosophical_accounts") or []), significance=strength.get("significance"),
                   p_value=p, dose_level=_as_tuple(edge.get("dose_level")), has_dose=bool(dose),
                   seasons=frozenset(te.get("observation_seasons") or []), mediators=tuple(mediators), spans=spans,
                   finding_ids=(finding_id,) if finding_id else (), merged_ids=(str(edge.get("id")),),
                   sentences=(sentence,) if sentence else ())


def _doc_of(edge: dict, g: dict, fallback: str) -> str:
    sd = edge.get("source_document")
    if isinstance(sd, dict):
        sd = sd.get("document_id")
    if sd:
        return str(sd)
    one = (g.get("source_document") or {}).get("document_id") if isinstance(g.get("source_document"), dict) else None
    if one:
        return str(one)
    docs = g.get("source_documents") or []
    if docs and isinstance(docs[0], dict) and docs[0].get("document_id"):
        return str(docs[0]["document_id"])
    return fallback


def load_graph(path, doc_id: Optional[str] = None) -> LoadedGraphs:
    """Load either format.  `doc_id` names the document for a wrapper file (default: the file stem)."""
    p = Path(path)
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    stem = p.name.split(".")[0]
    if isinstance(d, dict) and str(d.get("format", "")).startswith("interstitial-camo-graphs") and "graphs" in d:
        doc = doc_id or stem
        out = LoadedGraphs(str(p), "wrapper")
        for item in d["graphs"]:
            g = item.get("graph") or {}
            nodes = {n["id"]: n for n in g.get("nodes", [])}
            fid = str(item.get("finding_id"))
            out.findings_by_doc.setdefault(doc, []).append(fid)
            out.raw_graphs.append(g)
            for e in g.get("edges", []):
                rec = edge_record(e, nodes, doc, fid, item.get("sentence"))
                if rec:
                    out.edges_by_doc.setdefault(doc, []).append(rec)
        out.edges_by_doc.setdefault(doc, [])
        return out
    if not isinstance(d, dict) or "edges" not in d:
        raise ValueError(f"{path}: neither a CausalGraph nor an interstitial-camo-graphs wrapper")
    out = LoadedGraphs(str(p), "graph", raw_graphs=[d])
    nodes = {n["id"]: n for n in d.get("nodes", [])}
    for e in d.get("edges", []):
        doc = doc_id or _doc_of(e, d, stem)
        rec = edge_record(e, nodes, doc)
        if rec:
            out.edges_by_doc.setdefault(doc, []).append(rec)
    return out


def merge_loaded(items: List[LoadedGraphs]) -> Tuple[Dict[str, List[EdgeRec]], Dict[str, List[str]]]:
    edges: Dict[str, List[EdgeRec]] = {}
    findings: Dict[str, List[str]] = {}
    for it in items:
        for k, v in it.edges_by_doc.items():
            edges.setdefault(k, []).extend(v)
        for k, v in it.findings_by_doc.items():
            findings.setdefault(k, []).extend(v)
    return edges, findings


def load_doc_map(path) -> Dict[str, str]:
    m: Dict[str, str] = {}
    if not path:
        return m
    with open(path, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.reader(f)):
            if len(row) < 2 or not row[0].strip():
                continue
            if i == 0 and row[0].strip().lower() in ("gold_doc", "gold", "doc"):
                continue
            m[row[0].strip()] = row[1].strip()
    return m


# ---------------------------------------------------------------------------------------------- collapse mode
def collapse(edges: List[EdgeRec]) -> List[EdgeRec]:
    """Merge edges with the same subject, predicate, object and null flag (e.g. one claim split by dose level/season)."""
    groups: Dict[tuple, List[EdgeRec]] = {}
    for e in edges:
        groups.setdefault((e.subj.key(), e.predicate, e.obj.key(), e.null), []).append(e)
    out = []
    for members in groups.values():
        f = members[0]
        if len(members) == 1:
            out.append(f)
            continue
        sig = next((m.significance for m in members if m.significance not in (None, "not_reported", "not_tested")),
                   f.significance)
        out.append(replace(
            f, accounts=frozenset().union(*[m.accounts for m in members]),
            seasons=frozenset().union(*[m.seasons for m in members]),
            dose_level=tuple(sorted({x for m in members for x in m.dose_level})),
            has_dose=any(m.has_dose for m in members), significance=sig,
            spans=tuple(dict.fromkeys(s for m in members for s in m.spans)),
            finding_ids=tuple(dict.fromkeys(x for m in members for x in m.finding_ids)),
            merged_ids=tuple(x for m in members for x in m.merged_ids),
            sentences=tuple(dict.fromkeys(x for m in members for x in m.sentences))))
    return out
