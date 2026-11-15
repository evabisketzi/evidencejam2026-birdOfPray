"""Mechanical clean-up of a machine-made CAMO annotation, written as a NEW file (the input is never changed).

  python dev/annot_fix.py IN.yaml SLUG OUT.yaml [--report OUT.md]

What it does, and nothing else (no claim is added, removed or re-judged here):
  1. source_spans: finds every span text in the paper's markdown and sets start_char / end_char so that
     raw[start:end] is the span (the text is replaced by the verbatim markdown slice). A span that cannot be found is
     left as it is and reported.
  2. taxon nodes whose entity_term is a species name get the NCBITaxon ID from data/ncbitaxon_names.tsv.
  3. entity_term / measured_attribute: method detail in brackets is removed ("black plastic mulch (1.8 m wide) over
     planting rows" -> "black plastic mulch over planting rows"); the node name keeps the full wording.
  4. an edge that repeats another edge exactly (same nodes, predicate, null flag and sentence) is dropped.
  5. hand edits from dev/annot_v2/term_edits.tsv (slug, field, old, new): over-specified terms reduced to the entity.
  6. claim-level corrections from dev/annot_v2/edge_edits.yaml: a corrected original_sentence, and null results that a
     sentence states but the annotation only mentioned in its notes (added as edges cloned from the same sentence).
Every change is listed in the report.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.grounding import taxon_id  # noqa: E402

_TOK = re.compile(r"[A-Za-z0-9]+")
_CURIE = re.compile(r"[A-Za-z][\w.]*:\S+")
_TAG = re.compile(r"</?[A-Za-z][^<>]*>|\]\(#[^)]*\)|\\")           # html tags, markdown link targets, escapes: invisible in the clean text


def tokens(text: str):
    return [(m.group(0).lower(), m.start(), m.end()) for m in _TOK.finditer(text)]


def visible_tokens(raw: str):
    """Tokens of the markdown with markup removed, keeping raw offsets."""
    out = []
    pos = 0
    for m in _TAG.finditer(raw):
        out += [(t, a + pos, b + pos) for t, a, b in tokens(raw[pos:m.start()])]
        pos = m.end()
    out += [(t, a + pos, b + pos) for t, a, b in tokens(raw[pos:])]
    return out


def locate(raw: str, rtoks, index, text: str):
    """(start, end) of `text` in raw, matching on alphanumeric tokens; None if it is not there."""
    if text and text in raw:
        a = raw.index(text)
        return a, a + len(text)
    want = [t for t, _, _ in tokens(text)]
    if not want:
        return None
    joined = "".join(want)
    for i in index.get(want[0], []):                   # tokens may be split differently ("R2" vs "R <sup>2"): compare joined
        acc, j = "", i
        while j < len(rtoks) and len(acc) < len(joined):
            acc += rtoks[j][0]
            j += 1
        if acc == joined:
            a, b = rtoks[i][1], rtoks[j - 1][2]
            while b < len(raw):                                   # closing markup and punctuation belong to the span
                m = _TAG.match(raw, b)
                if m and m.end() > b:
                    b = m.end()
                elif raw[b] in ".!?)%\"'”’":
                    b += 1
                else:
                    break
            return a, b
    return None


def strip_brackets(term: str) -> str:
    out = term
    for _ in range(3):
        out = re.sub(r"\s*\([^()]*\)", "", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,;")
    return out or term


def fix(graph: dict, raw: str, edits=()):
    rep = {"spans fixed": [], "spans not found": [], "taxon IDs": [], "terms shortened": [], "hand edits": [], "duplicate edges dropped": []}
    rtoks = visible_tokens(raw)
    index: dict = {}
    for i, (t, _, _) in enumerate(rtoks):
        index.setdefault(t, []).append(i)
    for item in list(graph.get("nodes", [])) + list(graph.get("edges", [])):
        for sp in item.get("source_spans") or []:
            t = sp.get("text") or ""
            a, b = sp.get("start_char"), sp.get("end_char")
            if a is not None and b is not None and raw[a:b] == t:
                continue
            hit = locate(raw, rtoks, index, t)
            if hit is None:
                rep["spans not found"].append(f"{item['id']}: {t[:80]!r}")
                continue
            sp["start_char"], sp["end_char"] = hit
            sp["text"] = raw[hit[0]:hit[1]]
            rep["spans fixed"].append(item["id"])
    for n in graph.get("nodes", []):
        term = str(n.get("entity_term") or "")
        if n.get("entity_type") == "taxon" and term and not _CURIE.fullmatch(term):
            tid = taxon_id(term)
            if tid:
                n["entity_term"] = tid
                rep["taxon IDs"].append(f"{n['id']}: {term!r} -> {tid}")
                continue
        for key in ("entity_term", "measured_attribute"):
            v = n.get(key)
            if isinstance(v, str) and "(" in v and not _CURIE.fullmatch(v):
                new = strip_brackets(v)
                if new != v:
                    n[key] = new
                    rep["terms shortened"].append(f"{n['id']}.{key}: {v!r} -> {new!r}")
    for field, old, new in edits:
        hit = [n for n in graph.get("nodes", []) if n.get(field) == old]
        for n in hit:
            n[field] = new
        rep["hand edits"].append(f"{field}: {old!r} -> {new!r} ({len(hit)} node(s))" + ("" if hit else "  NOT FOUND"))
    seen, kept = set(), []
    for e in graph.get("edges", []):
        k = (e.get("subject"), e.get("predicate"), e.get("object"), bool(e.get("negated")), e.get("original_sentence"),
             repr(e.get("comparator")), repr(e.get("context_dependence")), repr(e.get("temporal_extent")), repr(e.get("dose")))
        if k in seen:
            rep["duplicate edges dropped"].append(e["id"])
            continue
        seen.add(k)
        kept.append(e)
    graph["edges"] = kept
    return rep


def apply_edge_edits(graph: dict, spec: dict, rep: dict) -> None:
    import copy
    edges = {e["id"]: e for e in graph["edges"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    rep["claim corrections"] = []
    for item in spec.get("set", []):
        for eid in item["edges"]:
            e = edges[eid]
            for k, v in item.items():
                if k != "edges":
                    e[k] = v
                    rep["claim corrections"].append(f"{eid}: {k} set to {str(v)[:90]!r}")
    gone = set(spec.get("delete", []))
    if gone:
        missing = gone - set(edges)
        if missing:
            raise SystemExit(f"edge_edits: no such edge(s) {sorted(missing)}")
        graph["edges"] = [e for e in graph["edges"] if e["id"] not in gone]
        text = yaml.safe_dump(graph["edges"], allow_unicode=True, width=10000)
        unused = [n["id"] for n in graph["nodes"] if n["id"] not in text]
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in unused]
        rep["claim corrections"] += [f"deleted (claim cited from another study): {i}" for i in sorted(gone)]
        rep["claim corrections"] += [f"node no longer used, removed: {i}" for i in unused]
    for add in spec.get("add_null", []):
        src = edges[add["clone"]]
        e = copy.deepcopy(src)
        e["id"] = add["id"]
        if "new_object" in add:
            no = add["new_object"]
            n = copy.deepcopy(nodes[no["clone"]])
            n.update({k: v for k, v in no.items() if k != "clone"})
            graph["nodes"].append(n)
            nodes[n["id"]] = n
            e["object"] = n["id"]
        else:
            e["object"] = add["object"]
        e.update(predicate="associated_with", negated=True, causal_language="no_relationship")
        for k in ("fcm_weight", "fcm_weight_source", "dose", "dose_level", "mediation", "moderation"):
            e.pop(k, None)
        if isinstance(e.get("strength"), dict):
            e["strength"] = {"status": e["strength"].get("status", "explicitly_asserted"), "significance": "not_significant"}
        e["annotation_notes"] = f"Added 2026-11-14 (annot_v2): null result stated in the same sentence as {src['id']}."
        graph["edges"].insert(graph["edges"].index(src) + 1, e)
        edges[e["id"]] = e
        rep["claim corrections"].append(f"added null edge {e['id']}: {nodes[e['subject']]['name']} -/-> {nodes[e['object']]['name']}")


def main(argv):
    src, slug, dst = Path(argv[0]), argv[1], Path(argv[2])
    report = Path(argv[argv.index("--report") + 1]) if "--report" in argv else None
    if dst.resolve() == src.resolve():
        raise SystemExit("refusing to overwrite the input")
    graph = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw = (ROOT / "corpus" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    edits = []
    ef = ROOT / "dev" / "annot_v2" / "term_edits.tsv"
    if ef.exists():
        for ln in ef.read_text(encoding="utf-8").splitlines():
            c = ln.split("\t")
            if len(c) == 4 and not ln.startswith("#") and c[0] == slug:
                edits.append((c[1], c[2], c[3]))
    rep = fix(graph, raw, edits)
    ee = ROOT / "dev" / "annot_v2" / "edge_edits.yaml"
    if ee.exists():
        spec = (yaml.safe_load(ee.read_text(encoding="utf-8")) or {}).get(slug)
        if spec:
            apply_edge_edits(graph, spec, rep)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(yaml.safe_dump(graph, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    lines = [f"## {slug} ({src.name})", ""]
    for k, v in rep.items():
        lines.append(f"- **{k}:** {len(v)}" + (f" (in {len(set(v))} nodes/edges)" if k == "spans fixed" and v else ""))
        if k != "spans fixed":
            lines += [f"  - {x}" for x in v]
    text = "\n".join(lines) + "\n"
    if report:
        with open(report, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
