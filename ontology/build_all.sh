#!/usr/bin/env bash
# build_all.sh - build every ontology index in one go (dev machine, run once).
#
#   ./build_all.sh                         # everything
#   ./build_all.sh --extra-taxa "Canis lupus"   # extra options go to build_ontology_indexes.py
#
# 1. Python: $PYTHON, else the active virtualenv, else <repo root>/.venv, else <repo root>/venv
#    (created if missing).
# 2. Installs <repo root>/requirements-dev.txt only if ijson/rapidfuzz/yaml/curies are not importable.
# 3. Downloads only the raw files missing from <repo root>/raw_json/ (NCBITaxon is 2.4 GB),
#    then builds all indexes into ontology_index/, NCBITaxon included.
# 4. Runs tests/test_grounding.py and prints what to commit.
# The repo root is the folder holding corpus/: this script's folder or the one above it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
[[ ! -d "$ROOT/corpus" && -d "$HERE/../corpus" ]] && ROOT="$(cd "$HERE/.." && pwd)"

if [[ -n "${PYTHON:-}" ]]; then PY="$PYTHON"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then PY="$VIRTUAL_ENV/bin/python"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"
else
    if [[ ! -x "$ROOT/venv/bin/python" ]]; then
        echo "== creating $ROOT/venv"
        python3 -m venv "$ROOT/venv"
    fi
    PY="$ROOT/venv/bin/python"
fi
echo "== python: $PY ($("$PY" --version 2>&1))"

if ! "$PY" -c "import ijson, rapidfuzz, yaml, curies" 2>/dev/null; then
    echo "== installing requirements-dev.txt"
    "$PY" -m pip install -q -r "$ROOT/requirements-dev.txt"
fi

echo "== building indexes (raw files: $ROOT/raw_json, corpus: $ROOT/corpus)"
mkdir -p "$ROOT/raw_json"
"$PY" "$HERE/build_ontology_indexes.py" --src-dir "$ROOT/raw_json" --corpus "$ROOT/corpus" \
    --download --ncbitaxon "$@"

if [[ -f "$HERE/tests/test_grounding.py" ]]; then
    echo "== tests"
    "$PY" "$HERE/tests/test_grounding.py"
fi

echo
echo "== done. Commit the indexes so clean checkouts need no raw files:"
echo "   git add $(realpath --relative-to="$PWD" "$HERE/ontology_index") && git commit -m 'Build ontology indexes'"
