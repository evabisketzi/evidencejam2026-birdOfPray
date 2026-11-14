#!/usr/bin/env bash
# Dev loop: run the pipeline on the two dev papers, then score against the gold.
#   dev/run_dev.sh [extra pipeline options, e.g. --thinking on | --prompt system_socratic.txt | --no-cache]
#   env: DEV_OUT (pipeline output dir, default dev/out), DEV_SCORE_OUT (scorer output dir, default dev/score_out)
#        DEV_SET=all  also the newer gold papers 3KPITIV3, 6HKWT4QG and ITXNQ843;  DEV_SET=new  only those three
# Needs BRINE_URL, BRINE_MODEL, BRINE_API_KEY.  Murphy = corpus slug YKQQZV93 (gold doc murphy2005, see dev/gold/doc_map.csv).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${DEV_OUT:-dev/out}"
SCORE="${DEV_SCORE_OUT:-dev/score_out}"
case "${DEV_SET:-orig}" in
  orig) DOCS=YKQQZV93,4CB9X9XE; GOLD=(--gold dev/gold/murphy2005.yaml --gold-doc-id murphy2005 --gold dev/gold/4CB9X9XE.camo.yaml) ;;
  new)  DOCS=3KPITIV3,6HKWT4QG,ITXNQ843;  GOLD=(--gold dev/gold/3KPITIV3.yaml --gold dev/gold/6HKWT4QG.yaml --gold dev/gold/ITXNQ843.yaml) ;;
  all)  DOCS=YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG,ITXNQ843
        GOLD=(--gold dev/gold/murphy2005.yaml --gold-doc-id murphy2005 --gold dev/gold/4CB9X9XE.camo.yaml --gold dev/gold/3KPITIV3.yaml --gold dev/gold/6HKWT4QG.yaml --gold dev/gold/ITXNQ843.yaml) ;;
  *) echo "DEV_SET must be orig, new or all" >&2; exit 2 ;;
esac
./run.sh corpus/ "$OUT" --docs "$DOCS" "$@"
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
mkdir -p "$SCORE"
.venv/bin/python -m dev.score.cli \
  "${GOLD[@]}" \
  --pred "$OUT/camo_graph.yaml" --doc-map dev/gold/doc_map.csv --tokens "$OUT/tokens.csv" --out "$SCORE/"
echo; echo "=== headline ==="
sed -n '/^## 1. Headline/,/^## 2/p' "$SCORE/score.md" | sed '$d'
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
SCORE="$SCORE" .venv/bin/python - <<'PY'
import json, os
d = json.load(open(os.path.join(os.environ["SCORE"], "score.json")))
m = d["score"]["modes"]["raw"]
for title, key in (("first 10 false negatives (gold edges we missed)", "fn"), ("first 10 false positives (our edges with no gold match)", "fp")):
    print(f"\n=== {title} ===")
    for i, x in enumerate(m[key][:10], 1):
        a, b = (x["gold"], x["best_candidate"]) if key == "fn" else (x["pred"], x["nearest_gold"])
        print(f"{i}. [{x['doc']}] {x['reason']}\n   {'gold' if key == 'fn' else 'ours'}: {a}\n   nearest: {b}")
PY
