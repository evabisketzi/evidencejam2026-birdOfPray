#!/usr/bin/env bash
# Unattended evaluation: baseline prompt vs Socratic prompt.
#
#   A  dev scores for both prompts on the two gold papers (no cache, real timings), pick a winner
#   B  full corpus run with the winning prompt (cached, so a crash resumes), then validation
#   C  full corpus run with the other prompt (skipped if B was too slow or it is already morning)
#   D  REPORT.md
#
# Usage: dev/overnight.sh [--limit N] [--resume RUN_DIR]
#   --limit N        only the first N papers in the full runs (to test this script against a mock endpoint)
#   --resume DIR     continue an earlier run folder; phases that finished (.done markers) are skipped
# Environment: BRINE_URL, BRINE_MODEL, BRINE_API_KEY (inherited, never written anywhere).
#   B_MAX_SECONDS (default 25200 = 7 h)   phase C is skipped if phase B took longer
#   DEADLINE_HHMM (default 07:30)         phase C is skipped if phase B ends after the next such time
# No `set -e`: one failing phase must never end the night.
set -uo pipefail
cd "$(dirname "$0")/.."

LIMIT=()
RESUME=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --limit) LIMIT=(--limit "$2"); shift 2 ;;
    --resume) RESUME="$2"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

START=$(date +%s)
if [ -n "$RESUME" ]; then RUN="$(realpath "$RESUME")"; else RUN="$(pwd)/dev/overnight/$(date +%Y%m%d_%H%M%S)"; fi
mkdir -p "$RUN"
ln -sfn "$RUN" dev/overnight/latest 2>/dev/null || true
LOG="$RUN/overnight.log"
PY=".venv/bin/python"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
record() { printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "${5:-}" >> "$RUN/phases.tsv"; }

# run one phase: phase NAME CMD...   (log to $RUN/NAME.log; marker .NAME.done on success; resumable)
phase() {
  local name="$1"; shift
  if [ -f "$RUN/.$name.done" ]; then log "phase $name: already done, skipping (resume)"; return 0; fi
  local t0 t1 rc
  t0=$(date +%s)
  log "phase $name: START"
  "$@" > "$RUN/$name.log" 2>&1
  rc=$?
  t1=$(date +%s)
  if [ "$rc" -eq 0 ]; then
    touch "$RUN/.$name.done"; record "$name" "$t0" "$t1" ok
    log "phase $name: END ok ($((t1 - t0)) s)"
  else
    record "$name" "$t0" "$t1" "failed" "exit code $rc; see $name.log"
    log "phase $name: END FAILED, exit code $rc ($((t1 - t0)) s); continuing"
  fi
  return "$rc"
}

# ------------------------------------------------------------------------------------------ pre-flight
log "overnight run folder: $RUN"
missing=""
for v in BRINE_URL BRINE_MODEL BRINE_API_KEY; do
  if [ -z "${!v:-}" ]; then missing="$missing $v"; fi
done
if [ -n "$missing" ]; then
  log "ABORT: missing environment variable(s):$missing (values are never printed)"; exit 2
fi
log "environment: BRINE_URL set, BRINE_MODEL set, BRINE_API_KEY set"

free_bytes=$(df --output=avail -B1 . | tail -1 | tr -d ' ')
if [ "${free_bytes:-0}" -lt 2147483648 ]; then
  log "ABORT: less than 2 GB free on this disk ($free_bytes bytes)"; exit 2
fi
log "disk: $((free_bytes / 1073741824)) GB free"

if [ ! -x "$PY" ]; then python3 -m venv .venv >> "$LOG" 2>&1; fi
$PY -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt >> "$LOG" 2>&1 \
  || log "WARNING: pip install -r requirements-dev.txt failed; continuing with what is installed"

if [ ! -f "$RUN/.tests.done" ]; then
  log "running the test suite (no tokens are spent before it passes)"
  t0=$(date +%s)
  if $PY -m pytest -q tests > "$RUN/tests.log" 2>&1; then
    touch "$RUN/.tests.done"; record tests "$t0" "$(date +%s)" ok; log "tests: $(tail -1 "$RUN/tests.log")"
  else
    record tests "$t0" "$(date +%s)" failed "see tests.log"
    log "ABORT: tests failed ($(tail -1 "$RUN/tests.log")); no tokens were spent"; exit 3
  fi
fi

C=4
if [ -f dev/concurrency_result.json ]; then
  C=$($PY -c 'import json; print(int(json.load(open("dev/concurrency_result.json"))["chosen"]))' 2>/dev/null || echo 4)
  log "concurrency C=$C (from dev/concurrency_result.json)"
else
  log "concurrency C=$C (default: no concurrency test result found)"
fi

# ------------------------------------------------------------------------------------------ phase A
for pair in "baseline:system.txt" "socratic:system_socratic.txt"; do
  name="${pair%%:*}"; file="${pair##*:}"
  DEV_OUT="$RUN/dev_$name" DEV_SCORE_OUT="$RUN/dev_$name/score" \
    phase "dev_$name" dev/run_dev.sh --prompt "$file" --no-cache --concurrency "$C"
done
phase dev_comparison $PY dev/overnight_report.py compare "$RUN"
WINNER_FILE="system.txt"
[ -f "$RUN/winner.txt" ] && WINNER_FILE="$(cat "$RUN/winner.txt")"
if [ "$WINNER_FILE" = "system_socratic.txt" ]; then W=socratic; O=baseline; OFILE=system.txt; else W=baseline; O=socratic; OFILE=system_socratic.txt; fi
log "winner: $W ($WINNER_FILE); see dev_comparison.md"

# ------------------------------------------------------------------------------------------ full runs
full_run() {   # full_run VARIANT PROMPT_FILE   -> run (retry once if it fails), then validate
  local v="$1" file="$2" out="$RUN/full_$1"
  ./run.sh corpus/ "$out" --prompt "$file" --concurrency "$C" ${LIMIT[@]+"${LIMIT[@]}"}
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "first attempt exited with $rc; retrying once (the cache makes this a resume)"
    local t0=$(date +%s)
    ./run.sh corpus/ "$out" --prompt "$file" --concurrency "$C" ${LIMIT[@]+"${LIMIT[@]}"}
    rc=$?
    record "full_${v}_retry" "$t0" "$(date +%s)" "$([ $rc -eq 0 ] && echo ok || echo failed)" "retry after exit code $rc"
  fi
  $PY -m pipeline.validate "$out"
  local vrc=$?
  echo "run exit code $rc, validation exit code $vrc"
  return $(( rc != 0 || vrc != 0 ))
}

B_START=$(date +%s)
phase "full_$W" full_run "$W" "$WINNER_FILE"
B_END=$(date +%s)
B_SECS=$(awk -F'\t' -v n="full_$W" '$1==n {s+=$3-$2} END {print s+0}' "$RUN/phases.tsv" 2>/dev/null)
[ -z "$B_SECS" ] && B_SECS=$((B_END - B_START))

# phase C: skip when B was too slow, or when it is already past the morning deadline
HHMM="${DEADLINE_HHMM:-07:30}"
DEADLINE=$(date -d "today $HHMM" +%s)
[ "$DEADLINE" -le "$START" ] && DEADLINE=$(date -d "tomorrow $HHMM" +%s)
B_MAX="${B_MAX_SECONDS:-25200}"
NOW=$(date +%s)
if [ -f "$RUN/.full_$O.done" ]; then
  log "phase full_$O: already done, skipping (resume)"
elif [ "$B_SECS" -gt "$B_MAX" ]; then
  log "phase full_$O: SKIPPED because phase B took $B_SECS s (more than $B_MAX s)"
  record "full_$O" "$NOW" "$NOW" skipped "phase B took $B_SECS s, more than $B_MAX s; endpoint and machine needed for tuning"
elif [ "$NOW" -gt "$DEADLINE" ]; then
  log "phase full_$O: SKIPPED because it is already past $HHMM ($(date -d "@$NOW" '+%H:%M'))"
  record "full_$O" "$NOW" "$NOW" skipped "phase B finished at $(date -d "@$NOW" '+%a %H:%M'), past the $HHMM deadline"
else
  phase "full_$O" full_run "$O" "$OFILE"
fi

# ------------------------------------------------------------------------------------------ phase D
phase report $PY dev/overnight_report.py report "$RUN"
log "DONE. Morning report: $RUN/REPORT.md"
