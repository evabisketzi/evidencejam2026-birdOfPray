#!/usr/bin/env bash
# Runs queued evaluation jobs on the four gold papers with the real endpoint.  Start ONCE, in a shell where BRINE_URL,
# BRINE_MODEL and BRINE_API_KEY are exported:      tmux new -d -s jobs 'dev/jobrunner.sh'
# A job is a file dev/jobs/queue/NAME.job with one line of key=value pairs; only these keys and values are accepted:
#   preprocess=sentence|paragraph|paragraph-chunks   prompt=<file in pipeline/prompt/>   cache=on|refresh|off   set=gold4|murphy
# Output: dev/jobs/out/NAME/ (+ NAME.log); the job file moves to dev/jobs/done/ or dev/jobs/failed/.  Nothing else is executed.
# Stop: create dev/jobs/STOP (or tmux kill-session -t jobs).  The key is inherited, never written anywhere.
set -uo pipefail
cd "$(dirname "$0")/.."
for v in BRINE_URL BRINE_MODEL BRINE_API_KEY; do [ -n "${!v:-}" ] || { echo "missing $v (value never printed)"; exit 2; }; done
Q=dev/jobs/queue; mkdir -p "$Q" dev/jobs/out dev/jobs/done dev/jobs/failed
echo "$(date '+%F %T') job runner started (pid $$)" | tee -a dev/jobs/runner.log
while [ ! -f dev/jobs/STOP ]; do
  job=$(ls "$Q"/*.job 2>/dev/null | head -1)
  if [ -z "$job" ]; then sleep 10; continue; fi
  name=$(basename "$job" .job)
  if ! [[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]]; then mv "$job" dev/jobs/failed/; continue; fi
  pre=sentence; prompt=system.txt; cache=on; set=gold4; bad=""
  for kv in $(head -1 "$job"); do
    k="${kv%%=*}"; v="${kv#*=}"
    case "$k" in
      preprocess) [[ "$v" =~ ^(sentence|paragraph|paragraph-chunks)$ ]] && pre="$v" || bad="$kv" ;;
      prompt) [[ "$v" =~ ^[A-Za-z0-9_.-]+$ ]] && [ -f "pipeline/prompt/$v" ] && prompt="$v" || bad="$kv" ;;
      cache) [[ "$v" =~ ^(on|refresh|off)$ ]] && cache="$v" || bad="$kv" ;;
      set) [[ "$v" =~ ^(gold4|murphy)$ ]] && set="$v" || bad="$kv" ;;
      *) bad="$kv" ;;
    esac
  done
  if [ -n "$bad" ]; then echo "$(date '+%F %T') $name REJECTED ($bad)" | tee -a dev/jobs/runner.log; mv "$job" dev/jobs/failed/; continue; fi
  docs=YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG; [ "$set" = murphy ] && docs=YKQQZV93
  flags=(); [ "$cache" = refresh ] && flags=(--refresh-cache); [ "$cache" = off ] && flags=(--no-cache)
  echo "$(date '+%F %T') $name START preprocess=$pre prompt=$prompt cache=$cache set=$set" | tee -a dev/jobs/runner.log
  if ./run.sh corpus/ "dev/jobs/out/$name" --docs "$docs" --preprocess "$pre" --prompt "$prompt" --concurrency 8 "${flags[@]}" > "dev/jobs/out/$name.log" 2>&1; then
    mv "$job" dev/jobs/done/; echo "$(date '+%F %T') $name DONE" | tee -a dev/jobs/runner.log
  else
    mv "$job" dev/jobs/failed/; echo "$(date '+%F %T') $name FAILED (see dev/jobs/out/$name.log)" | tee -a dev/jobs/runner.log
  fi
done
echo "$(date '+%F %T') job runner stopped" | tee -a dev/jobs/runner.log
