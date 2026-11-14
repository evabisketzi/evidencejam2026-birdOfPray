"""python -m pipeline.main corpus/ output/ [--docs SLUG,...] [--limit N] [--concurrency 4] [--thinking on|off] [--prompt FILE]

Stages: 1 preprocess -> 2 grounding -> 3 LLM extraction -> 4 parse + expand -> 5 guard + merge -> 6 write + validate.
One paper failing never stops the run; every paper in corpus/index.csv still gets a source_documents entry."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from .expand import expand_claims
from .extract import Client, ConfigError, DEFAULT_PROMPT, LLMError, config_from_env, extract_paper, load_prompt
from .guard import guard_paper, merge
from .preprocess.assemble import Options, process_paper
from .preprocess.legend import load_taxon_table
from .preprocess.tokens import get_counter
from .write import summary, validate_outputs, write_outputs

log = logging.getLogger("pipeline")


def read_index(corpus: Path) -> List[Dict[str, str]]:
    with open(corpus / "index.csv", encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("slug")]


def process_one(row: Dict[str, str], corpus: Path, client: Client, system: str, count, table, max_input_tokens: int) -> dict:
    slug = row["slug"]
    out = {"doc": slug, "error": None, "prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0, "chunks": 0,
           "nodes": {}, "edges": [], "stats": {}}
    t0 = time.time()
    try:
        raw = (corpus / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
        pre = process_paper(slug, raw, row, count, Options(), table)                          # stage 1 (+2: legend IDs)
        valid = [s["n"] for s in pre.sidecar["sentences"]]
        if not valid:
            raise RuntimeError("preprocessing kept no sentences")
        ex = extract_paper(client, system, pre.txt, valid, max_input_tokens)                  # stage 3
        out.update(prompt_tokens=ex.prompt_tokens, completion_tokens=ex.completion_tokens, seconds=ex.seconds, chunks=ex.chunks)
        exp = expand_claims(slug, ex.claims, pre.sidecar)                                     # stage 4
        nodes, edges, stats = guard_paper(slug, exp.nodes, exp.edges)                         # stage 5 (per paper)
        out.update(nodes=nodes, edges=edges, stats=dict(stats))
        out["counts"] = {"sentences": len(valid), "claims": len(ex.claims), "bad_lines": ex.n_bad, "repaired": ex.n_repaired,
                         "dropped_lines": ex.n_dropped_lines, "dropped_sentence_refs": ex.n_dropped_sentences,
                         "edges_expanded": len(exp.edges), "edges_kept": len(edges)}
        out["modes"] = sorted(set(ex.modes))
    except Exception as e:  # noqa: BLE001 - isolate every paper
        out["error"] = f"{type(e).__name__}: {e}"
        log.warning("%s failed: %s", slug, out["error"])
        log.debug("%s", traceback.format_exc())
    out["wall"] = time.time() - t0
    return out


def run(corpus: Path, out_dir: Path, docs: Optional[List[str]] = None, limit: Optional[int] = None, concurrency: int = 4,
        thinking: bool = False, prompt: str = DEFAULT_PROMPT, use_cache: bool = True, max_input_tokens: int = 12000,
        max_tokens: int = 3000) -> int:
    t0 = time.time()
    cfg = config_from_env(thinking, use_cache, max_tokens)                 # raises ConfigError if a variable is missing
    pname, system = load_prompt(prompt)
    index = read_index(corpus)
    todo = [r for r in index if not docs or r["slug"] in docs]
    if docs:
        missing = sorted(set(docs) - {r["slug"] for r in index})
        if missing:
            raise ConfigError(f"--docs not in index.csv: {', '.join(missing)}")
    if limit:
        todo = todo[:limit]
    count, tok_name = get_counter(allow_download=False)
    table = load_taxon_table()
    client = Client(cfg)
    log.info("prompt=%s thinking=%s tokenizer=%s papers=%d concurrency=%d", pname, "on" if thinking else "off", tok_name, len(todo), concurrency)
    outcomes: List[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futs = [pool.submit(process_one, r, corpus, client, system, count, table, max_input_tokens) for r in todo]
        for f in futs:
            outcomes.append(f.result())
            done += 1
            if done % 10 == 0 or done == len(futs):
                log.info("%d/%d papers done (%d failed)", done, len(futs), sum(1 for o in outcomes if o["error"]))
    per_doc = {o["doc"]: (o["nodes"], o["edges"]) for o in outcomes}
    graph = merge(index, per_doc)                                          # raises if there is not a single edge
    yp, jp = write_outputs(graph, out_dir)
    errors, validators = validate_outputs(graph, yp, jp)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "tokens.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc", "prompt_tokens", "completion_tokens", "seconds", "chunks", "thinking"])
        for o in outcomes:
            w.writerow([o["doc"], o["prompt_tokens"], o["completion_tokens"], f"{o['seconds']:.2f}", o["chunks"], "on" if thinking else "off"])
    with open(out_dir / "run_log.json", "w", encoding="utf-8") as f:
        json.dump({"prompt": pname, "thinking": "on" if thinking else "off", "model": cfg.model, "tokenizer": tok_name,
                   "papers": [{k: v for k, v in o.items() if k not in ("nodes", "edges")} for o in outcomes]}, f, indent=1)
    print(summary(graph, outcomes, time.time() - t0, validators))
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} problems):", file=sys.stderr)
        for e in errors[:20]:
            print("  " + e, file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.main", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("output")
    ap.add_argument("--docs", help="comma-separated slugs (default: all)")
    ap.add_argument("--limit", type=int, help="only the first N papers")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--thinking", choices=("on", "off"), default="off")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="file in pipeline/prompt/ (default system.txt)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--max-input-tokens", type=int, default=12000)
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        return run(Path(a.corpus), Path(a.output), [d.strip() for d in a.docs.split(",") if d.strip()] if a.docs else None, a.limit,
                   a.concurrency, a.thinking == "on", a.prompt, not a.no_cache, a.max_input_tokens, a.max_tokens)
    except (ConfigError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2 if isinstance(e, ConfigError) else 1


if __name__ == "__main__":
    sys.exit(main())
