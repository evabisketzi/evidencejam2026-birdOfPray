#!/usr/bin/env python3
"""
select_terms.py - let the LLM choose among the grounding candidates found by ground_terms.py.

Only terms the deterministic step could not settle (status "ambiguous" or "needs_review")
are sent, in one call per report (= per article when the pipeline grounds article by
article; larger reports are split into batches of --batch terms). Articles with nothing to
decide make no call.

The model sees each term with its node name, a short source excerpt and at most 5 numbered
candidates (CURIE, label, how it matched, parents/lineage, short definition) and answers
with candidate NUMBERS only: {"T1": 2, "T2": 0}. Numbers are mapped back to CURIEs here, so
the model never types an ID and cannot invent one. Anything unparseable or out of range
counts as "none", and the term stays free text.

Decisions on non-taxon terms are memoised by (kind, normalised text, candidate CURIEs) in
ontology_index/selection_memo.json, so "abundance" is decided once for the whole corpus.
Taxon decisions are not memoised: homonyms (Morus the plant / Morus the bird) depend on
the article.

LLM: the LiteLLM endpoint from the environment (BRINE_URL, BRINE_MODEL, BRINE_API_KEY),
called with a plain HTTP POST to its /chat/completions route; no LLM SDK is needed.

Usage
  python select_terms.py report.json --graph llm_output.json --out grounded.json
  python select_terms.py report.json --dry-run          # print the prompts, call nothing

In code:
  selections, stats = select_candidates(report)          # {term key: CURIE or None}
  grounded = apply_groundings(doc, report, selections)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from ground_terms import INDEX_DIR, apply_groundings, dump_doc, load_doc, norm_key, term_key

PENDING = {"ambiguous", "needs_review"}
MAX_CANDIDATES = 5
DEF_CHARS = 120
SPAN_CHARS = 200
MAX_SPANS = 2
DEFAULT_MEMO = INDEX_DIR / "selection_memo.json"

SYSTEM_PROMPT = """\
You map terms from an ecology paper to ontology terms. For each term, give the number of the
candidate that means the same thing as the term in its context, or 0 if none does.
- Same meaning, not just shared words. A broader candidate is acceptable only when the term is
  plainly a kind of it AND nothing closer is listed ("seed germination rate" -> "seed
  germination" is fine; "biomass" -> "organic material" is not).
- Taxa: use the lineage and the context to pick between homonyms. Never map a species to its
  genus: answer 0 instead.
- measured_attribute: pick a quality only if it is the property that was measured.
Reply with JSON only, one key per term, e.g. {"T1": 2, "T2": 0}"""

LLMFn = Callable[[str, str, int], tuple[str, dict]]


def _clip(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def _excerpt(span: str, mentions: list[str], n: int = SPAN_CHARS) -> str:
    """A window of the span centred on the first mention of the term."""
    span = re.sub(r"\s+", " ", span).strip()
    if len(span) <= n:
        return span
    low = span.lower()
    pos = next((low.find(m.lower()) for m in mentions if m and low.find(m.lower()) >= 0), 0)
    start = max(0, min(pos - n // 2, len(span) - n))
    return ("..." if start else "") + span[start:start + n] + ("..." if start + n < len(span) else "")


def render_candidate(i: int, c: dict) -> str:
    parts = [f"{i} {c['curie']} {c['label']}"]
    how = c["match_type"]
    if c.get("matched_text") and c["matched_text"].lower() != c["label"].lower():
        how += f' "{_clip(c["matched_text"], 60)}"'
    if how.startswith("fuzzy"):
        how += f" {c['score']:.0f}"
    parts.append(how)
    if "rank" in c:                                               # taxon
        parts.append(c.get("rank") or "?")
        if c.get("lineage"):
            parts.append(" > ".join(c["lineage"][-4:]))
    else:
        if c.get("parents"):
            parts.append("is_a: " + "; ".join(c["parents"][:2]))
        if c.get("definition"):
            parts.append("def: " + _clip(c["definition"], DEF_CHARS))
    return "   " + " | ".join(parts)


def render_term(tid: str, g: dict) -> str:
    lines = [f'{tid} [{g["kind"]}] "{g["query"]}"']
    if g.get("node_names"):
        lines.append("   node: " + "; ".join(f'"{_clip(n, 100)}"' for n in g["node_names"][:2]))
    for span in g.get("context", [])[:MAX_SPANS]:
        lines.append(f'   context: "{_excerpt(span, g.get("mentions", []) + [g["query"]])}"')
    for i, c in enumerate(g["candidates"][:MAX_CANDIDATES], 1):
        lines.append(render_candidate(i, c))
    return "\n".join(lines)


def parse_reply(text: str, expected: dict[str, int]) -> dict[str, int]:
    """{term id: candidate number}; only ids we sent, only numbers in range."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    raw: dict = {}
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        try:
            raw = json.loads(match.group(0))
        except json.JSONDecodeError:
            raw = {}
    if not raw:
        raw = {f"T{a}": b for a, b in re.findall(r'"?T(\d+)"?\s*[:=]\s*"?(\d+)', text)}
    out = {}
    for tid, value in raw.items():
        try:
            n = int(value)
        except (TypeError, ValueError):
            continue
        if tid in expected and 0 <= n <= expected[tid]:
            out[tid] = n
    return out


def litellm_url() -> str:
    """Chat-completions route of the LiteLLM proxy in BRINE_URL. LiteLLM serves it both at
    /chat/completions and /v1/chat/completions, so BRINE_URL may end in /v1 or not."""
    base = os.environ["BRINE_URL"].rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


_SEND_THINKING_SWITCH = True       # set False once the proxy has rejected chat_template_kwargs


def _post_json(url: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['BRINE_API_KEY']}",
        "User-Agent": "camo-grounding/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def brine_llm(system: str, user: str, max_tokens: int) -> tuple[str, dict]:
    """One chat call to the LiteLLM endpoint named by BRINE_URL / BRINE_MODEL / BRINE_API_KEY.
    Plain HTTP (standard library), no LLM SDK. Returns (reply text, usage + finish_reason)."""
    global _SEND_THINKING_SWITCH
    body = {"model": os.environ["BRINE_MODEL"],
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user + "\n/no_think"}],
            "temperature": 0, "max_tokens": max_tokens}
    if _SEND_THINKING_SWITCH:
        # Qwen3: switch thinking off (chat-template kwarg, forwarded by LiteLLM to vLLM/SGLang)
        body["chat_template_kwargs"] = {"enable_thinking": False}
    try:
        data = _post_json(litellm_url(), body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 400 and "chat_template_kwargs" in body and "chat_template_kwargs" in detail:
            _SEND_THINKING_SWITCH = False                     # proxy refuses it: rely on /no_think
            body.pop("chat_template_kwargs")
            data = _post_json(litellm_url(), body)
        else:
            raise RuntimeError(f"HTTP {exc.code} from LiteLLM: {detail}") from None
    choice = (data.get("choices") or [{}])[0]
    usage = dict(data.get("usage") or {})
    usage["finish_reason"] = choice.get("finish_reason")
    return (choice.get("message") or {}).get("content") or "", usage


def memo_key(g: dict) -> str:
    cands = ",".join(sorted(c["curie"] for c in g["candidates"][:MAX_CANDIDATES]))
    return f"{g['kind']}|{norm_key(g['query'])}|{cands}"


def select_candidates(report: dict, llm: LLMFn | None = brine_llm, memo: dict | None = None,
                      batch: int = 20, log: Callable[[str], None] | None = None) -> tuple[dict, dict]:
    """Ask the LLM about every pending term in the report. With llm=None nothing is sent
    (dry run: the prompts are passed to `log`). Returns (selections, stats)."""
    log = log or (lambda msg: print(msg, file=sys.stderr))
    memo = {} if memo is None else memo
    selections: dict[str, str | None] = {}
    stats = {"pending": 0, "memo_hits": 0, "asked": 0, "chosen": 0, "calls": 0,
             "prompt_tokens": 0, "completion_tokens": 0, "unparsed_calls": 0}
    todo = []
    for g in report["terms"]:
        if g["status"] not in PENDING or not g.get("candidates"):
            continue
        stats["pending"] += 1
        key = g.get("key") or term_key(g)
        if g["kind"] != "taxon" and memo_key(g) in memo:
            selections[key] = memo[memo_key(g)]
            stats["memo_hits"] += 1
        else:
            todo.append(g)
    for start in range(0, len(todo), batch):
        chunk = todo[start:start + batch]
        ids = {f"T{i}": g for i, g in enumerate(chunk, 1)}
        user = "\n\n".join(render_term(tid, g) for tid, g in ids.items())
        if llm is None:
            log(f"--- system ---\n{SYSTEM_PROMPT}\n--- user ---\n{user}\n")
            continue
        try:
            text, usage = llm(SYSTEM_PROMPT, user, 8 * len(chunk) + 20)
        except Exception as exc:                                  # endpoint down: keep free text
            log(f"WARNING: LLM call failed ({exc}); {len(chunk)} terms stay free text")
            continue
        stats["calls"] += 1
        stats["asked"] += len(chunk)
        stats["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        stats["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        answers = parse_reply(text, {tid: min(len(g["candidates"]), MAX_CANDIDATES) for tid, g in ids.items()})
        if not answers:
            stats["unparsed_calls"] += 1
            log(f"WARNING: could not parse LLM reply ({usage.get('finish_reason')}): {text[:200]!r}")
        for tid, g in ids.items():
            n = answers.get(tid)
            if n is None:                                         # no usable answer: don't memoise
                continue
            curie = g["candidates"][n - 1]["curie"] if n > 0 else None
            selections[g.get("key") or term_key(g)] = curie
            stats["chosen"] += curie is not None
            if g["kind"] != "taxon":
                memo[memo_key(g)] = curie
    return selections, stats


def load_memo(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_memo(memo: dict, path: Path) -> None:
    path.write_text(json.dumps(memo, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", help="grounding report from ground_terms.py")
    ap.add_argument("--graph", help="the document the report was made from")
    ap.add_argument("--out", help="write the document with resolved + selected CURIEs (needs --graph)")
    ap.add_argument("--selections", default="selections.json", help="where to write {term key: CURIE}")
    ap.add_argument("--memo", default=str(DEFAULT_MEMO))
    ap.add_argument("--no-memo", action="store_true")
    ap.add_argument("--batch", type=int, default=20, help="terms per LLM call")
    ap.add_argument("--dry-run", action="store_true", help="print the prompts; call nothing")
    args = ap.parse_args()

    with open(args.report, encoding="utf-8") as fh:
        report = json.load(fh)
    memo_path = Path(args.memo)
    memo = {} if args.no_memo else load_memo(memo_path)
    if not args.dry_run:
        missing = [v for v in ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY") if not os.environ.get(v)]
        if missing:
            sys.exit(f"set {', '.join(missing)} (or use --dry-run)")
    selections, stats = select_candidates(report, None if args.dry_run else brine_llm, memo, args.batch)
    print("stats: " + json.dumps(stats), file=sys.stderr)
    if args.dry_run:
        return
    if not args.no_memo:
        save_memo(memo, memo_path)
    with open(args.selections, "w", encoding="utf-8") as fh:
        json.dump(selections, fh, indent=2, ensure_ascii=False)
    if args.out:
        if not args.graph:
            sys.exit("--out needs --graph")
        dump_doc(apply_groundings(load_doc(args.graph), report, selections), args.out)


if __name__ == "__main__":
    main()
