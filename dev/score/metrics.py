"""P/R/F1, per-field diagnostics and validity checks."""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from .load import EdgeRec, collapse
from .match import DEFAULT_THRESHOLD, DocMatch, entity_agree, match_document
from .normalise import ROOT, STOP
from .report import readable_edge

LEVELS = ("strict", "standard", "loose")
LANGS = ("direct_causal", "uncertain_causal", "associational", "no_relationship")


def prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def ratio(n: int, d: int) -> Optional[float]:
    return n / d if d else None


# ----------------------------------------------------------------------------------------------- pair stats
def _words(t: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(w) > 3 and w not in STOP}


def grounded(g: EdgeRec, p: EdgeRec) -> Optional[bool]:
    """Character-span overlap when both sides have positions, else word overlap (>= 0.5 of the gold's content words)."""
    gs = [(a, b) for a, b, _ in g.spans if a is not None and b is not None]
    ps = [(a, b) for a, b, _ in p.spans if a is not None and b is not None]
    if gs and ps:
        return any(a1 < b2 and a2 < b1 for a1, b1 in gs for a2, b2 in ps)
    gt = " ".join(g.sentences) or " ".join(t for *_, t in g.spans)
    pt = " ".join(p.sentences) or " ".join(t for *_, t in p.spans)
    gw, pw = _words(gt), _words(pt)
    if not gw or not pw:
        return None
    return len(gw & pw) / len(gw) >= 0.5


@dataclass
class PairStats:
    n: int = 0
    predicate: int = 0
    lang: int = 0
    sig_n: int = 0
    sig: int = 0
    acc_n: int = 0
    acc_sum: float = 0.0
    taxon_n: int = 0
    taxon: int = 0
    ground_n: int = 0
    ground: int = 0
    attr_exact: int = 0
    attr_wrong: int = 0
    attr_unverifiable: int = 0
    etype_n: int = 0
    etype: int = 0
    confusion: Counter = field(default_factory=Counter)

    def add(self, o: "PairStats") -> None:
        for k, v in o.__dict__.items():
            if k == "confusion":
                self.confusion.update(v)
            else:
                setattr(self, k, getattr(self, k) + v)

    def observe(self, g: EdgeRec, p: EdgeRec) -> None:
        self.n += 1
        self.predicate += g.predicate == p.predicate
        self.lang += g.causal_language == p.causal_language
        self.confusion[(g.causal_language or "none", p.causal_language or "none")] += 1
        if g.significance is not None:
            self.sig_n += 1
            self.sig += g.significance == p.significance
        if g.accounts or p.accounts:
            self.acc_n += 1
            self.acc_sum += len(g.accounts & p.accounts) / len(g.accounts | p.accounts)
        for gn, pn in ((g.subj, p.subj), (g.obj, p.obj)):
            if gn.primary_taxon:
                self.taxon_n += 1
                self.taxon += gn.primary_taxon in pn.taxa_ids
            if pn.attr_id:
                if gn.attr_id == pn.attr_id:
                    self.attr_exact += 1
                elif gn.attr_id:
                    self.attr_wrong += 1
                else:
                    self.attr_unverifiable += 1
            if gn.entity_type is not None and pn.entity_type is not None:
                self.etype_n += 1
                self.etype += gn.entity_type == pn.entity_type
        gr = grounded(g, p)
        if gr is not None:
            self.ground_n += 1
            self.ground += gr

    def summary(self) -> Dict:
        n_attr = self.attr_exact + self.attr_wrong + self.attr_unverifiable
        return {
            "matched_pairs": self.n,
            "predicate_accuracy": ratio(self.predicate, self.n),
            "causal_language_accuracy": ratio(self.lang, self.n),
            "significance_accuracy": ratio(self.sig, self.sig_n), "significance_n": self.sig_n,
            "accounts_jaccard": (self.acc_sum / self.acc_n) if self.acc_n else None, "accounts_n": self.acc_n,
            "taxon_id_accuracy": ratio(self.taxon, self.taxon_n), "taxon_id_n": self.taxon_n,
            "attribute_ids": {"predicted": n_attr, "exact": self.attr_exact, "wrong": self.attr_wrong,
                              "unverifiable": self.attr_unverifiable,
                              "precision_all": ratio(self.attr_exact, n_attr),
                              "precision_verifiable": ratio(self.attr_exact, self.attr_exact + self.attr_wrong)},
            "grounding_rate": ratio(self.ground, self.ground_n), "grounding_n": self.ground_n,
            "entity_type_agreement": ratio(self.etype, self.etype_n), "entity_type_n": self.etype_n,
        }


# ----------------------------------------------------------------------------------------------- per document
@dataclass
class DocResult:
    doc: str
    pred_doc: str
    n_gold: int
    n_pred: int
    levels: Dict[str, Dict]
    null: Dict
    findings: Optional[Dict]
    pairs: PairStats
    predicate_usage: Counter
    fn: List[Dict]
    fp: List[Dict]
    match: DocMatch = field(repr=False, default=None)


def _reason(pair, null_mismatch: bool = False) -> Tuple[str, str]:
    """(code, human text) for an edge without a standard match."""
    if pair is None:
        if null_mismatch:
            return "null_mismatch", "right entities, but one side is a null result and the other a positive claim (null flags disagree)"
        return "no_loose_match", "no loose match (the pair of entities was not found)"
    if pair.opposite:
        return "opposite_direction", "right entities, opposite direction"
    return "attribute_differs", f"right entities, object attribute differs (similarity {pair.obj_attr:.2f})"


def _null_mismatch(g, P) -> bool:
    return any(g.null != p.null and entity_agree(g.subj, p.subj) and entity_agree(g.obj, p.obj) for p in P)


def _doc_result(doc, pred_doc, G, P, findings, threshold) -> DocResult:
    m = match_document(G, P, threshold)
    levels = {}
    for lv in LEVELS:
        tp = len(m.level(lv))
        levels[lv] = prf(tp, len(P) - tp, len(G) - tp)
    std = m.level("standard")
    gm = {p.i for p in std}
    pm = {p.j for p in std}
    gn = [i for i, g in enumerate(G) if g.null]
    pn = [j for j, p in enumerate(P) if p.null]
    null = {"gold_null": len(gn), "pred_null": len(pn), "matched": sum(1 for i in gn if i in gm),
            "recall": ratio(sum(1 for i in gn if i in gm), len(gn)),
            "precision": ratio(sum(1 for j in pn if j in pm), len(pn))}
    find = None
    if findings:
        fset = list(dict.fromkeys(findings))
        found = {f for p in std for f in G[p.i].finding_ids}
        find = {"n": len(fset), "found": sum(1 for f in fset if f in found),
                "recall": ratio(sum(1 for f in fset if f in found), len(fset)),
                "missed": [f for f in fset if f not in found]}
    ps = PairStats()
    for p in std:
        ps.observe(G[p.i], P[p.j])
    by_g = {p.i: p for p in m.pairs}
    by_p = {p.j: p for p in m.pairs}
    fn_list, fp_list = [], []
    for i, g in enumerate(G):
        if i in gm:
            continue
        lp = by_g.get(i)
        best = lp.j if lp else (int(m.near[i].argmax()) if len(P) else None)
        sim = (lp.obj_attr if lp else (float(m.near[i, best]) if best is not None else None))
        code, text = _reason(lp, _null_mismatch(g, P)) if best is not None else ("no_prediction", "no predicted edges for this document")
        fn_list.append({"doc": doc, "finding": ", ".join(g.finding_ids) or None, "gold_edge": g.edge_id,
                        "sentence": (g.sentences[0] if g.sentences else None), "gold": readable_edge(g),
                        "best_candidate": readable_edge(P[best]) if best is not None else None, "best_sim": sim,
                        "reason": text, "reason_code": code})
    for j, p in enumerate(P):
        if j in pm:
            continue
        lp = by_p.get(j)
        best = lp.i if lp else (int(m.near[:, j].argmax()) if len(G) else None)
        sim = (lp.obj_attr if lp else (float(m.near[best, j]) if best is not None else None))
        code, text = _reason(lp, any(g.null != p.null and entity_agree(g.subj, p.subj) and entity_agree(g.obj, p.obj) for g in G)) if len(G) else ("no_gold", "no gold edges")
        fp_list.append({"doc": doc, "pred_edge": p.edge_id, "sentence": (p.sentences[0] if p.sentences else None),
                        "pred": readable_edge(p), "nearest_gold": readable_edge(G[best]) if best is not None else None,
                        "nearest_sim": sim, "reason": text, "reason_code": code})
    return DocResult(doc, pred_doc, len(G), len(P), levels, null, find, ps, Counter(p.predicate for p in P), fn_list, fp_list, m)


# ----------------------------------------------------------------------------------------------- whole run
def _micro(results: List[DocResult]) -> Dict:
    out: Dict = {"n_gold": sum(r.n_gold for r in results), "n_pred": sum(r.n_pred for r in results), "levels": {}}
    for lv in LEVELS:
        out["levels"][lv] = prf(sum(r.levels[lv]["tp"] for r in results), sum(r.levels[lv]["fp"] for r in results),
                                sum(r.levels[lv]["fn"] for r in results))
    gn = sum(r.null["gold_null"] for r in results)
    pn = sum(r.null["pred_null"] for r in results)
    mm = sum(r.null["matched"] for r in results)
    # predicted nulls that matched = matched nulls (a null can only match a null)
    out["null"] = {"gold_null": gn, "pred_null": pn, "matched": mm, "recall": ratio(mm, gn), "precision": ratio(mm, pn)}
    fr = [r.findings for r in results if r.findings]
    out["findings"] = ({"n": sum(f["n"] for f in fr), "found": sum(f["found"] for f in fr),
                        "recall": ratio(sum(f["found"] for f in fr), sum(f["n"] for f in fr))} if fr else None)
    ps = PairStats()
    for r in results:
        ps.add(r.pairs)
    out["pairs"] = ps.summary()
    out["confusion"] = {g: {p: ps.confusion.get((g, p), 0) for p in LANGS + ("none",)} for g in LANGS + ("none",)}
    use = Counter()
    for r in results:
        use.update(r.predicate_usage)
    tot = sum(use.values())
    out["diagnostics"] = {"pred_edges_per_gold_edge": (out["n_pred"] / out["n_gold"]) if out["n_gold"] else None,
                          "predicate_share": {k: v / tot for k, v in use.most_common()} if tot else {},
                          "entity_type_agreement": out["pairs"]["entity_type_agreement"]}
    return out


def doc_dict(r: DocResult) -> Dict:
    d = {"doc": r.doc, "pred_doc": r.pred_doc, "n_gold": r.n_gold, "n_pred": r.n_pred, "levels": r.levels,
         "null": r.null, "findings": r.findings, "pairs": r.pairs.summary()}
    if r.n_pred == 0:
        d["warning"] = "no predicted edges for this document"
    return d


def score(gold_edges: Dict[str, List[EdgeRec]], gold_findings: Dict[str, List[str]], pred_edges: Dict[str, List[EdgeRec]],
          docmap: Optional[Dict[str, str]] = None, threshold: float = DEFAULT_THRESHOLD, tokens: Optional[Dict[str, Tuple[int, int]]] = None,
          sensitivity: Sequence[float] = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)) -> Dict:
    docmap = docmap or {}
    out: Dict = {"threshold": threshold, "docs": sorted(gold_edges), "modes": {}, "sensitivity": {}}
    out["unscored_pred_docs"] = sorted(set(pred_edges) - {docmap.get(d, d) for d in gold_edges})
    for mode in ("raw", "collapse"):
        results: List[DocResult] = []
        for doc in sorted(gold_edges):
            pdoc = docmap.get(doc, doc)
            G, P = gold_edges[doc], pred_edges.get(pdoc, [])
            if mode == "collapse":
                G, P = collapse(G), collapse(P)
            results.append(_doc_result(doc, pdoc, G, P, gold_findings.get(doc), threshold))
        micro = _micro(results)
        out["modes"][mode] = {"docs": {r.doc: doc_dict(r) for r in results}, "micro": micro,
                              "fn": [x for r in results for x in r.fn], "fp": [x for r in results for x in r.fp]}
        sens = {}
        for t in sorted(set(list(sensitivity) + [threshold])):
            tp = sum(len(r.match.level('standard', t)) for r in results)
            tps = {lv: sum(len(r.match.level(lv, t)) for r in results) for lv in LEVELS}
            sens[f"{t:g}"] = {**prf(tp, micro["n_pred"] - tp, micro["n_gold"] - tp),
                              "strict_f1": prf(tps["strict"], micro["n_pred"] - tps["strict"], micro["n_gold"] - tps["strict"])["f1"]}
        out["sensitivity"][mode] = sens
        if tokens:
            per = []
            for r in results:
                tk = tokens.get(r.pred_doc) or tokens.get(r.doc)
                if tk:
                    per.append(tk[0] + tk[1])
            if per:
                mean = sum(per) / len(per)
                f1 = micro["levels"]["standard"]["f1"]
                out["modes"][mode]["tokens"] = {"papers_with_tokens": len(per), "mean_tokens_per_paper": mean,
                                                "standard_f1": f1, "f1_per_1k_tokens": f1 / (mean / 1000) if mean else None}
    return out


def load_tokens(path) -> Dict[str, Tuple[int, int]]:
    import csv
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["doc"]] = (int(float(row.get("prompt_tokens") or 0)), int(float(row.get("completion_tokens") or 0)))
    return out


# ----------------------------------------------------------------------------------------------- validity
@lru_cache(maxsize=1)
def schema_prefixes() -> Optional[set]:
    p = ROOT / "schema" / "causalmosaic.yaml"
    if not p.exists():
        return None
    return set((yaml.safe_load(p.read_text(encoding="utf-8")).get("prefixes") or {}).keys())


_CURIE = re.compile(r"^([A-Za-z][A-Za-z0-9_.\-]*):[^\s/].*$")


def validity_checks(graphs: Iterable[dict]) -> Dict:
    """Counts of structural problems in a prediction.  `graphs` = CausalGraph dicts."""
    prefixes = schema_prefixes()
    c = Counter()
    examples: Dict[str, List[str]] = {}

    def hit(key: str, what: str) -> None:
        c[key] += 1
        examples.setdefault(key, [])
        if len(examples[key]) < 5:
            examples[key].append(what)

    for g in graphs:
        nodes = g.get("nodes") or []
        edges = g.get("edges") or []
        ids = Counter(n.get("id") for n in nodes)
        for k, v in ids.items():
            if v > 1:
                hit("duplicate_node_ids", str(k))
        for k, v in Counter(e.get("id") for e in edges).items():
            if v > 1:
                hit("duplicate_edge_ids", str(k))
        node_ids = set(ids)
        docs = {d.get("document_id") for d in (g.get("source_documents") or []) if isinstance(d, dict)}
        by_id = {n.get("id"): n for n in nodes}
        for e in edges:
            for side in ("subject", "object"):
                if e.get(side) not in node_ids:
                    hit(f"dangling_{side}", f"{e.get('id')} -> {e.get(side)}")
            for m in (e.get("mediation") or {}).get("mediator_node_ids") or []:
                if m not in node_ids:
                    hit("dangling_mediator", f"{e.get('id')} -> {m}")
            for m in (e.get("moderation") or {}).get("moderator_node_ids") or []:
                if m not in node_ids:
                    hit("dangling_moderator", f"{e.get('id')} -> {m}")
            sd = e.get("source_document")
            if isinstance(sd, str) and docs and sd not in docs:
                hit("dangling_source_document", f"{e.get('id')} -> {sd}")
            if e.get("negated") and e.get("causal_language") != "no_relationship":
                hit("negated_without_no_relationship", str(e.get("id")))
            if e.get("causal_language") == "no_relationship" and not e.get("negated"):
                hit("no_relationship_without_negated", str(e.get("id")))
            if e.get("negated") or e.get("causal_language") == "no_relationship":
                o = by_id.get(e.get("object")) or {}
                if o.get("state_or_change_qualifier") == "unchanged":
                    hit("unchanged_on_null_object", str(e.get("id")))
            unit = (e.get("dose") or {}).get("unit")
            if unit is not None and not re.match(r"^(unit|UO):", str(unit)):
                hit("bad_dose_unit", f"{e.get('id')}: {unit}")
        if prefixes is not None:
            vals = []
            for n in nodes:
                vals += [n.get("entity_term"), n.get("measured_attribute")]
                vals += [a.get("entity_term") for a in n.get("applied_to") or [] if isinstance(a, dict)]
            for e in edges:
                vals.append((e.get("dose") or {}).get("unit"))
                vals.append(((e.get("dose") or {}).get("counted_entity") or {}).get("entity_term"))
            for v in vals:
                m = _CURIE.match(str(v)) if v else None
                if m and not str(v).startswith(("http://", "https://")) and m.group(1) not in prefixes:
                    hit("undeclared_prefix", str(v))
    keys = ["dangling_subject", "dangling_object", "dangling_mediator", "dangling_moderator", "dangling_source_document",
            "duplicate_node_ids", "duplicate_edge_ids", "undeclared_prefix", "negated_without_no_relationship",
            "no_relationship_without_negated", "unchanged_on_null_object", "bad_dose_unit"]
    return {"counts": {k: c.get(k, 0) for k in keys}, "examples": examples, "total": sum(c.values()),
            "prefix_check": "skipped (schema not found)" if prefixes is None else "done"}


def linkml_validate(pred_path: str) -> Dict:
    schema = ROOT / "schema" / "causalmosaic.yaml"
    try:
        r = subprocess.run(["linkml-validate", "-s", str(schema), "-C", "CausalGraph", pred_path], capture_output=True,
                           text=True, timeout=1800)
        lines = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip() and "Warning" not in ln and "warn" not in ln.lower()]
        errors = [ln for ln in lines if "[ERROR]" in ln]
        return {"ok": r.returncode == 0 and not errors, "returncode": r.returncode, "n_errors": len(errors),
                "first_errors": errors[:10], "output_tail": lines[-3:]}
    except FileNotFoundError:
        return {"ok": None, "error": "linkml-validate not installed (pip install -r requirements-dev.txt)"}
    except subprocess.TimeoutExpired:
        return {"ok": None, "error": "linkml-validate timed out"}
