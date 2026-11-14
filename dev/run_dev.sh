#!/usr/bin/env bash
# Dev loop: run the pipeline on the two dev papers, then score against the gold.
#   dev/run_dev.sh [extra pipeline options, e.g. --thinking on | --prompt system_socratic.txt | --no-cache]
# Needs BRINE_URL, BRINE_MODEL, BRINE_API_KEY.  Murphy = corpus slug YKQQZV93 (gold doc murphy2005, see dev/gold/doc_map.csv).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${DEV_OUT:-dev/out}"
./run.sh corpus/ "$OUT" --docs YKQQZV93,4CB9X9XE "$@"
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
mkdir -p dev/score_out
.venv/bin/python -m dev.score.cli \
  --gold dev/gold/murphy2005.yaml --gold-doc-id murphy2005 --gold dev/gold/4CB9X9XE.camo.yaml \
  --pred "$OUT/camo_graph.yaml" --doc-map dev/gold/doc_map.csv --tokens "$OUT/tokens.csv" --out dev/score_out/
echo; echo "=== headline ==="
sed -n '/^## 1. Headline/,/^## 2/p' dev/score_out/score.md | sed '$d'
echo "=== tokens per paper ==="
.venv/bin/python - "$OUT/tokens.csv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
rows = [r for r in rows if int(r["prompt_tokens"]) or int(r["completion_tokens"])]
for r in rows:
    print(f"{r['doc']}: prompt {r['prompt_tokens']}  completion {r['completion_tokens']}  seconds {r['seconds']}  chunks {r['chunks']}  thinking {r['thinking']}")
if rows:
    n = len(rows)
    print(f"mean per paper: prompt {sum(int(r['prompt_tokens']) for r in rows)/n:.0f}  completion {sum(int(r['completion_tokens']) for r in rows)/n:.0f}")
PY
.venv/bin/python - <<'PY'
import json
d = json.load(open("dev/score_out/score.json"))
m = d["score"]["modes"]["raw"]
for title, key in (("first 10 false negatives (gold edges we missed)", "fn"), ("first 10 false positives (our edges with no gold match)", "fp")):
    print(f"\n=== {title} ===")
    for i, x in enumerate(m[key][:10], 1):
        a, b = (x["gold"], x["best_candidate"]) if key == "fn" else (x["pred"], x["nearest_gold"])
        print(f"{i}. [{x['doc']}] {x['reason']}\n   {'gold' if key == 'fn' else 'ours'}: {a}\n   nearest: {b}")
PY
