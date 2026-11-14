#!/usr/bin/env bash
# Stage 1 'sentence' (sentence-level filtering, ours) vs 'paragraph' (paragraph scoring and selection, the teammate's), on the two gold papers, real endpoint, baseline prompt, cache bypassed, REPS repeats each (alternating).
#   dev/compare_preprocess.sh [--reps N] [--concurrency N] [--prompt FILE] [--out DIR] [--variants "sentence paragraph paragraph-chunks"] [--set orig|new|all]
#   --out an existing folder adds the new variants next to the runs already there (finished runs are skipped).
# Environment: BRINE_URL, BRINE_MODEL, BRINE_API_KEY (inherited, never written anywhere).
set -uo pipefail
cd "$(dirname "$0")/.."
REPS=3; C=8; VARIANTS="sentence paragraph"; PROMPT=system.txt; OUT="dev/preproc_compare/$(date +%Y%m%d_%H%M%S)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --reps) REPS="$2"; shift 2 ;; --concurrency) C="$2"; shift 2 ;; --prompt) PROMPT="$2"; shift 2 ;; --out) OUT="$2"; shift 2 ;; --variants) VARIANTS="$2"; shift 2 ;; --set) export DEV_SET="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
for v in BRINE_URL BRINE_MODEL BRINE_API_KEY; do [ -n "${!v:-}" ] || { echo "missing $v (value never printed)"; exit 2; }; done
mkdir -p "$OUT"; echo "output: $OUT"
for r in $(seq 1 "$REPS"); do
  for pp in $VARIANTS; do
    d="$OUT/${pp}_$r"
    [ -f "$d/.done" ] && { echo "skip $pp rep $r (done)"; continue; }
    echo "=== $(date '+%H:%M:%S') $pp rep $r"
    DEV_OUT="$d" DEV_SCORE_OUT="$d/score" dev/run_dev.sh --preprocess "$pp" --prompt "$PROMPT" --no-cache --concurrency "$C" > "$d.log" 2>&1 \
      && touch "$d/.done" || echo "  $pp rep $r FAILED (see $d.log)"
  done
done
.venv/bin/python dev/preproc_compare_report.py "$OUT" | tee "$OUT/COMPARE.md"
