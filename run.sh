#!/usr/bin/env bash
# One command, from a clean checkout:   ./run.sh corpus/ output/ [--concurrency 4] [--limit N] [--docs SLUG,...] ...
# Needs BRINE_URL, BRINE_MODEL and BRINE_API_KEY in the environment (never hard-coded, the key is never logged).
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: ./run.sh CORPUS_DIR OUTPUT_DIR [options]   (see: python -m pipeline.main --help)" >&2
  exit 2
fi
missing=""
for v in BRINE_URL BRINE_MODEL BRINE_API_KEY; do
  if [ -z "${!v:-}" ]; then missing="$missing $v"; fi
done
if [ -n "$missing" ]; then
  echo "error: missing environment variable(s):$missing" >&2
  echo "       set BRINE_URL (endpoint), BRINE_MODEL (model name) and BRINE_API_KEY (key)" >&2
  exit 2
fi

corpus="$(realpath -m "$1")"
output="$(realpath -m "$2")"
shift 2
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
exec .venv/bin/python -m pipeline.main "$corpus" "$output" "$@"
