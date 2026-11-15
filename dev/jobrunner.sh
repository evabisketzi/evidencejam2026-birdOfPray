#!/usr/bin/env bash
# Runs queued evaluation jobs with the real endpoint, up to PARALLEL at a time.  Start ONCE, in a shell where BRINE_URL,
# BRINE_MODEL and BRINE_API_KEY are exported:      tmux new -d -s jobs 'dev/jobrunner.sh'
# A job is a file dev/jobs/queue/NAME.job (NAME: letters, digits, _ . -) with one line of key=value pairs, oldest first.
# Only these keys and values are accepted (anything else: the job is REJECTED and logged, the runner keeps going):
#   preprocess=sentence|paragraph|paragraph-chunks   prompt=<file in pipeline/prompt/>   cache=on|refresh|off
#   set=gold8|gold5|gold4|murphy|all   thinking=on|off   max_tokens=<1000-16000>   refine=on|off   samples=1|2|3
#   ontology=off|lookup|select   ontology_fields=all|entities   (stage 5b; unset = the pipeline default, lookup + all)
# refine=on / samples=2|3 become --refine / --samples N only if the CURRENT pipeline has those flags (checked per job, so a
# flag added later works without restarting the runner; otherwise the job is REJECTED); refine=off and samples=1 are the
# pipeline defaults and pass no flag.  A job whose pipeline rejects a flag anyway (argparse error) FAILS with the reason
# in dev/jobs/runner.log.
# Output: dev/jobs/out/NAME/ (+ NAME.log); the job file moves queue/ -> running/ -> done/ or failed/.  A NAME whose output
# directory already exists is rejected (results are never overwritten).  Nothing but ./run.sh is executed.
# Stop: create dev/jobs/STOP: no new jobs start, running ones finish, then the runner exits (or tmux kill-session -t jobs;
# jobs left in running/ go back to the queue at the next start).  The key is inherited, never written anywhere.
# JOBS_DIR=<dir> uses another jobs directory (tests).  SKIP_FLAG_CHECK=1 skips the --help check (tests the argparse path).
set -uo pipefail
cd "$(dirname "$0")/.."
PARALLEL=2
J="${JOBS_DIR:-dev/jobs}"
Q="$J/queue"; R="$J/running"; LOG="$J/runner.log"
for v in BRINE_URL BRINE_MODEL BRINE_API_KEY; do [ -n "${!v:-}" ] || { echo "missing $v (value never printed)"; exit 2; }; done
mkdir -p "$Q" "$R" "$J/out" "$J/done" "$J/failed"
exec 9>"$J/.runner.lock"
flock -n 9 || { echo "another job runner already uses $J"; exit 3; }
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

log "job runner started (pid $$, up to $PARALLEL jobs at a time, jobs dir $J)"
for f in "$R"/*.job; do
  [ -e "$f" ] || continue
  mv "$f" "$Q/" && log "$(basename "$f" .job) REQUEUED (the runner stopped while it was running)"
done

has_flag() {   # does the current pipeline accept this flag?
  [ "${SKIP_FLAG_CHECK:-0}" = 1 ] && return 0
  .venv/bin/python -m pipeline.main --help 2>/dev/null | grep -qE -- "$1([ =,]|$)"
}

# parse "$1" (job file) into ARGS / DESC; on a bad key or value set BAD and return 1
parse_job() {
  local pre=sentence prompt=system.txt cache=on set=gold5 thinking="" maxtok="" refine="" samples="" onto="" ofields="" kv k v
  BAD=""; ARGS=(); DESC=""
  for kv in $(head -1 "$1"); do
    k="${kv%%=*}"; v="${kv#*=}"
    [ "$k" = "$kv" ] && { BAD="$kv (not key=value)"; return 1; }
    case "$k" in
      preprocess) [[ "$v" =~ ^(sentence|paragraph|paragraph-chunks)$ ]] && pre="$v" || BAD="$kv" ;;
      prompt) [[ "$v" =~ ^[A-Za-z0-9_.-]+$ ]] && [ -f "pipeline/prompt/$v" ] && prompt="$v" || BAD="$kv" ;;
      cache) [[ "$v" =~ ^(on|refresh|off)$ ]] && cache="$v" || BAD="$kv" ;;
      set) [[ "$v" =~ ^(gold8|gold5|gold4|murphy|all)$ ]] && set="$v" || BAD="$kv" ;;
      thinking) [[ "$v" =~ ^(on|off)$ ]] && thinking="$v" || BAD="$kv" ;;
      refine) [[ "$v" =~ ^(on|off)$ ]] && refine="$v" || BAD="$kv" ;;
      samples) [[ "$v" =~ ^[123]$ ]] && samples="$v" || BAD="$kv" ;;
      max_tokens) [[ "$v" =~ ^[0-9]{4,5}$ ]] && [ "$v" -ge 1000 ] && [ "$v" -le 16000 ] && maxtok="$v" || BAD="$kv" ;;
      ontology) [[ "$v" =~ ^(off|lookup|select)$ ]] && onto="$v" || BAD="$kv" ;;
      ontology_fields) [[ "$v" =~ ^(all|entities)$ ]] && ofields="$v" || BAD="$kv" ;;
      *) BAD="$kv (unknown key)" ;;
    esac
    [ -n "$BAD" ] && return 1
  done
  ARGS=(--preprocess "$pre" --prompt "$prompt" --concurrency 8)
  case "$set" in
    gold8) ARGS+=(--docs YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG,ITXNQ843,2F76GVEE,4C479SU8,V3H4MP29) ;;
    gold5) ARGS+=(--docs YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG,ITXNQ843) ;;
    gold4) ARGS+=(--docs YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG) ;;
    murphy) ARGS+=(--docs YKQQZV93) ;;
  esac
  [ "$cache" = refresh ] && ARGS+=(--refresh-cache)
  [ "$cache" = off ] && ARGS+=(--no-cache)
  [ -n "$thinking" ] && ARGS+=(--thinking "$thinking")
  [ -n "$maxtok" ] && ARGS+=(--max-tokens "$maxtok")
  if [ "$refine" = on ]; then                       # refine=off = the pipeline default: no flag
    has_flag --refine || { BAD="refine=on (this pipeline has no --refine yet)"; return 1; }
    ARGS+=(--refine)
  fi
  if [ -n "$samples" ] && [ "$samples" != 1 ]; then   # samples=1 = the pipeline default: no flag
    has_flag --samples || { BAD="samples=$samples (this pipeline has no --samples yet)"; return 1; }
    ARGS+=(--samples "$samples")
  fi
  if [ -n "$onto$ofields" ]; then
    has_flag --ontology || { BAD="ontology (this pipeline has no --ontology)"; return 1; }
    [ -n "$onto" ] && ARGS+=(--ontology "$onto")
    [ -n "$ofields" ] && ARGS+=(--ontology-fields "$ofields")
  fi
  DESC="preprocess=$pre prompt=$prompt cache=$cache set=$set${thinking:+ thinking=$thinking}${maxtok:+ max_tokens=$maxtok}"
  DESC+="${refine:+ refine=$refine}${samples:+ samples=$samples}${onto:+ ontology=$onto}${ofields:+ ontology_fields=$ofields}"
  return 0
}

run_job() {    # runs in the background: $1 name, rest = pipeline arguments
  local name="$1"; shift
  local out="$J/out/$name" jl="$J/out/$name.log" t0=$SECONDS rc why
  ./run.sh corpus/ "$out" "$@" > "$jl" 2>&1
  rc=$?
  if [ "$rc" = 0 ]; then
    mv "$R/$name.job" "$J/done/"; log "$name DONE in $((SECONDS - t0)) s"
  else
    why=$(grep -m1 -E "error: (unrecognized arguments|argument .*invalid choice|the following arguments)" "$jl" | cut -c1-160)
    mv "$R/$name.job" "$J/failed/"
    if [ -n "$why" ]; then log "$name FAILED: pipeline rejected a flag ($why)"
    else log "$name FAILED (exit $rc after $((SECONDS - t0)) s; see $jl)"; fi
  fi
}

while :; do
  running=$(jobs -rp | wc -l)
  if [ -f "$J/STOP" ]; then
    [ "$running" -eq 0 ] && break
    sleep 5; continue
  fi
  # every queued job, oldest first: bad ones are rejected at once (even while all slots are busy), good ones start
  # while a slot is free, the rest wait for the next pass
  while IFS= read -r job; do
    [ -f "$job" ] || continue
    name=$(basename "$job" .job)
    if ! [[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]]; then mv "$job" "$J/failed/"; log "$name REJECTED (bad job name)"; continue; fi
    if [ -e "$J/out/$name" ] || [ -e "$J/out/$name.log" ]; then mv "$job" "$J/failed/"; log "$name REJECTED (output $J/out/$name already exists)"; continue; fi
    if ! parse_job "$job"; then mv "$job" "$J/failed/"; log "$name REJECTED ($BAD)"; continue; fi
    [ "$running" -ge "$PARALLEL" ] && continue
    mv "$job" "$R/" || continue
    log "$name START $DESC"
    run_job "$name" "${ARGS[@]}" &
    running=$((running + 1))
  done < <(ls -1tr "$Q"/*.job 2>/dev/null)
  sleep 5
done
wait
log "job runner stopped"
