"""Markdown + JSON report."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

LANGS = ("direct_causal", "uncertain_causal", "associational", "no_relationship", "none")


def readable_node(n) -> str:
    name = n.name or n.id
    q = n.qualifier
    if q:
        name = re.sub(rf"^{re.escape(q)}\s+", "", name, flags=re.I)
        return f"[{q.capitalize()}] {name}"
    return name


def readable_edge(e) -> str:
    """[Increased] Sanguinaria canadensis initial planting density --causes--> [Decreased] Alliaria petiolata seedling count (NULL)"""
    s = f"{readable_node(e.subj)} --{e.predicate}--> {readable_node(e.obj)}"
    return s + (" (NULL)" if e.null else "")


def f(x, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _headline_rows(res: Dict) -> List[tuple]:
    rows = []
    for lv in ("strict", "standard", "loose"):
        for k, lab in (("precision", "P"), ("recall", "R"), ("f1", "F1")):
            rows.append((f"Edges {lv} {lab}", lambda m, lv=lv, k=k: m["micro"]["levels"][lv][k]))
    rows += [
        ("Null results precision", lambda m: m["micro"]["null"]["precision"]),
        ("Null results recall", lambda m: m["micro"]["null"]["recall"]),
        ("Finding recall", lambda m: (m["micro"]["findings"] or {}).get("recall")),
        ("causal_language accuracy", lambda m: m["micro"]["pairs"]["causal_language_accuracy"]),
        ("Taxon ID accuracy", lambda m: m["micro"]["pairs"]["taxon_id_accuracy"]),
    ]
    return rows


def _doc_table(mode: Dict) -> List[str]:
    h = ("| doc | gold | pred | strict F1 | std P | std R | std F1 | loose F1 | null P | null R | finding R | lang acc | taxon acc |\n"
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    out = [h]
    for d, r in mode["docs"].items():
        L, p = r["levels"], r["pairs"]
        out.append(f"| {d} | {r['n_gold']} | {r['n_pred']} | {f(L['strict']['f1'])} | {f(L['standard']['precision'])} | "
                   f"{f(L['standard']['recall'])} | {f(L['standard']['f1'])} | {f(L['loose']['f1'])} | {f(r['null']['precision'])} | "
                   f"{f(r['null']['recall'])} | {f((r['findings'] or {}).get('recall'))} | {f(p['causal_language_accuracy'])} | "
                   f"{f(p['taxon_id_accuracy'])} |" + (" ⚠ no predicted edges" if r.get("warning") else ""))
    return out


def _trunc(s: Optional[str], n: int = 170) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def to_markdown(res: Dict, validity: Optional[Dict], validate: Optional[Dict], primary: str, max_errors: int = 25,
                meta: Optional[Dict] = None) -> str:
    raw, col = res["modes"]["raw"], res["modes"]["collapse"]
    L: List[str] = ["# CAMO dev score", ""]
    if meta:
        L += [f"- gold: {', '.join(meta.get('gold', []))}", f"- prediction: {meta.get('pred')}"]
    L += [f"- object-attribute threshold (standard level): **{res['threshold']}**. Gates: loose = entities agree + null flags agree; "
          f"standard = loose + object attribute ≥ threshold + object directions not opposite; strict = standard + object directions equal",
          f"- documents scored: {', '.join(res['docs'])}",
          f"- raw mode: {raw['micro']['n_gold']} gold / {raw['micro']['n_pred']} predicted edges; "
          f"collapse mode (duplicate subject-predicate-object merged): {col['micro']['n_gold']} gold / {col['micro']['n_pred']} predicted",
          f"- error lists and the confusion matrix below use **{primary}** mode (`--collapse` switches to collapse)"]
    if res.get("unscored_pred_docs"):
        L.append(f"- predicted documents ignored (not in the gold): {len(res['unscored_pred_docs'])}")
    L += ["", "## 1. Headline", "", "| metric | raw | collapse |", "|---|---:|---:|"]
    for lab, fn in _headline_rows(res):
        L.append(f"| {lab} | {f(fn(raw))} | {f(fn(col))} |")
    for mode_name, m in (("raw", raw), ("collapse", col)):
        if "tokens" in m:
            t = m["tokens"]
            L.append(f"| tokens per paper ({mode_name}) | {t['mean_tokens_per_paper']:.0f} | |")
            L.append(f"| standard F1 per 1k tokens ({mode_name}) | {f(t['f1_per_1k_tokens'], 3)} | |")
    L += ["", "### Threshold sensitivity (object-attribute threshold; micro F1)", "", "| threshold | standard raw | standard collapse | strict raw | strict collapse |", "|---:|---:|---:|---:|---:|"]
    for t in res["sensitivity"]["raw"]:
        L.append(f"| {t} | {f(res['sensitivity']['raw'][t]['f1'])} | {f(res['sensitivity']['collapse'][t]['f1'])} | "
                 f"{f(res['sensitivity']['raw'][t]['strict_f1'])} | {f(res['sensitivity']['collapse'][t]['strict_f1'])} |")
    L += ["", "## 2. Per document", "", "### raw", ""] + _doc_table(raw) + ["", "### collapse", ""] + _doc_table(col)
    m = (raw if primary == "raw" else col)
    cm = m["micro"]["confusion"]
    L += ["", f"## 3. causal_language confusion ({primary}, matched pairs; rows = gold, columns = predicted)", "",
          "| gold \\ pred | " + " | ".join(LANGS) + " |", "|---|" + "---:|" * len(LANGS)]
    for g in LANGS:
        L.append(f"| {g} | " + " | ".join(str(cm[g][p]) for p in LANGS) + " |")
    p = m["micro"]["pairs"]
    L += ["", f"### Matched-pair diagnostics ({primary}, standard level, {p['matched_pairs']} pairs)", "",
          f"- predicate accuracy {f(p['predicate_accuracy'])}; causal_language accuracy {f(p['causal_language_accuracy'])}; "
          f"significance accuracy {f(p['significance_accuracy'])} (n={p['significance_n']})",
          f"- philosophical_accounts Jaccard {f(p['accounts_jaccard'])} (n={p['accounts_n']})",
          f"- taxon ID accuracy {f(p['taxon_id_accuracy'])} (n={p['taxon_id_n']} gold nodes with an NCBITaxon ID)",
          f"- attribute IDs predicted {p['attribute_ids']['predicted']}: exact {p['attribute_ids']['exact']}, wrong "
          f"{p['attribute_ids']['wrong']}, unverifiable (gold is free text) {p['attribute_ids']['unverifiable']}; precision "
          f"{f(p['attribute_ids']['precision_verifiable'])} on verifiable, {f(p['attribute_ids']['precision_all'])} on all",
          f"- grounding {f(p['grounding_rate'])} (n={p['grounding_n']} pairs with comparable spans/sentences)",
          f"- diagnostics (no score): entity_type agreement {f(p['entity_type_agreement'])}; predicted edges per gold edge "
          f"{f(m['micro']['diagnostics']['pred_edges_per_gold_edge'], 2)}; predicate share "
          + ", ".join(f"{k} {v:.0%}" for k, v in m["micro"]["diagnostics"]["predicate_share"].items())]
    fn = m["fn"]
    L += ["", f"## 4. Missed gold edges (false negatives, {primary}): {len(fn)}", ""]
    for i, x in enumerate(fn[:max_errors], 1):
        L += [f"{i}. **{x['doc']}**{' · finding ' + x['finding'] if x['finding'] else ''}",
              f"   - gold sentence: “{_trunc(x['sentence'])}”",
              f"   - gold: `{_trunc(x['gold'], 260)}`",
              f"   - why missed: {x['reason']}",
              f"   - best predicted candidate: `{_trunc(x['best_candidate'], 260) if x['best_candidate'] else '(none predicted for this document)'}`"
              + (f" (similarity {x['best_sim']:.2f})" if x["best_sim"] is not None else "")]
    if len(fn) > max_errors:
        L.append(f"\n… {len(fn) - max_errors} more in score.json")
    fp = m["fp"]
    L += ["", f"## 5. Unmatched predictions (false positives, {primary}): {len(fp)}", ""]
    for i, x in enumerate(fp[:max_errors], 1):
        L += [f"{i}. **{x['doc']}** · {x['pred_edge']}",
              f"   - predicted sentence: “{_trunc(x['sentence'])}”",
              f"   - predicted: `{_trunc(x['pred'], 260)}`",
              f"   - why unmatched: {x['reason']}",
              f"   - nearest gold: `{_trunc(x['nearest_gold'], 260) if x['nearest_gold'] else '(none)'}`"
              + (f" (similarity {x['nearest_sim']:.2f})" if x["nearest_sim"] is not None else "")]
    if len(fp) > max_errors:
        L.append(f"\n… {len(fp) - max_errors} more in score.json")
    L += ["", "## 6. Validity of the prediction file", ""]
    if validity is None:
        L.append("(not run)")
    else:
        L += ["| check | count |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in validity["counts"].items()]
        for k, ex in validity["examples"].items():
            L.append(f"\n- {k}, e.g.: " + "; ".join(ex[:3]))
        if validity.get("prefix_check", "done") != "done":
            L.append(f"\n- prefix check {validity['prefix_check']}")
    if validate is not None:
        L += ["", "### linkml-validate", "", f"- ok: **{validate.get('ok')}**" + (f" ({validate.get('n_errors')} errors)" if "n_errors" in validate else "")
              + (f" — {validate.get('error')}" if validate.get("error") else "")]
        for e in validate.get("first_errors", []):
            L.append(f"  - `{_trunc(e, 200)}`")
    return "\n".join(L) + "\n"


def write_reports(out_dir, res: Dict, validity: Optional[Dict], validate: Optional[Dict], primary: str, max_errors: int = 25,
                  meta: Optional[Dict] = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta or {}, "primary_mode": primary, "score": res, "validity": validity, "linkml_validate": validate}
    (out / "score.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    (out / "score.md").write_text(to_markdown(res, validity, validate, primary, max_errors, meta), encoding="utf-8")
