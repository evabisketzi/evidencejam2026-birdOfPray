#!/usr/bin/env bash
# Submission preflight: does the committed HEAD work from a clean checkout, the way the judges will run it?
#   dev/preflight.sh [--full] [--ref REF]
#     --full   run all 308 papers through the mock endpoint (about 15 min) instead of 5
#     --ref    commit/branch to check (default HEAD)
# Uses a throwaway git worktree and a local MOCK endpoint (no tokens, no key needed). Exit 0 = all checks passed.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"; FULL=0; REF=HEAD
while [ "$#" -gt 0 ]; do case "$1" in --full) FULL=1; shift ;; --ref) REF="$2"; shift 2 ;; *) echo "unknown option $1"; exit 2 ;; esac; done
SHA=""; TMP="$(mktemp -d)"; WT="$TMP/checkout"; PORT=$((18000 + RANDOM % 1000)); FAIL=0
ok()   { echo "  PASS  $*"; }
bad()  { echo "  FAIL  $*"; FAIL=1; }
warn() { echo "  WARN  $*"; }
cleanup() { [ -n "${MOCK:-}" ] && kill "$MOCK" 2>/dev/null; git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$TMP"; }
trap cleanup EXIT

SHA=$(git rev-parse --short "$REF"); echo "== preflight for $SHA ($(git log -1 --format=%s "$REF" | cut -c1-70))"
echo "-- repository state"
[ -z "$(git status --porcelain --untracked-files=no)" ] && ok "no uncommitted changes to tracked files" || warn "uncommitted changes to tracked files are NOT part of $REF"
up=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)
if [ -n "$up" ]; then
  git fetch -q "${up%%/*}" 2>/dev/null
  [ "$(git rev-list --count "$up..$REF" 2>/dev/null)" = 0 ] && ok "$REF is pushed ($up)" || warn "$REF has commits not on $up (judging uses the team repo)"
  case "$up" in team/*) ok "upstream is the team repo" ;; *) warn "upstream $up is not the team repo" ;; esac
else warn "no upstream branch set"; fi
now=$(date -u +%s); dl=$(date -u -d '2026-11-15 23:00' +%s); left=$(( (dl - now) / 3600 ))
[ "$left" -gt 0 ] && ok "judging snapshot in about $left h (Sun Nov 15, 6 p.m. EST)" || warn "the judging deadline has passed"

echo "-- clean checkout of $REF"
git worktree add -q --detach "$WT" "$SHA" || { bad "git worktree add failed"; exit 1; }
cd "$WT"
[ -x run.sh ] && ok "run.sh exists and is executable" || bad "run.sh missing or not executable"
unpinned=$(grep -vE '^\s*(#|$|-r )' requirements.txt | grep -vE '==' || true)
[ -z "$unpinned" ] && ok "requirements.txt fully pinned ($(grep -cE '==' requirements.txt) packages)" || bad "unpinned requirements: $unpinned"
if grep -rqE '\bsk-[A-Za-z0-9_-]{20,}|BRINE_API_KEY\s*=\s*["'"'"']?[A-Za-z0-9_-]{12,}' --include='*' . --exclude-dir=.git 2>/dev/null; then
  bad "a key-like string is committed (run: git grep -nE 'sk-|BRINE_API_KEY=')"; else ok "no key-like strings in the checkout"; fi
for f in corpus/index.csv schema/causalmosaic.yaml; do [ -f "$f" ] && ok "$f present" || bad "$f missing"; done

echo "-- run.sh without credentials must fail clearly"
out=$(env -u BRINE_URL -u BRINE_MODEL -u BRINE_API_KEY ./run.sh corpus/ "$TMP/nokey" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q BRINE_ && ok "exit $rc and names the missing variable" || bad "run.sh without credentials: exit $rc"

echo "-- end-to-end run against the mock endpoint (fresh .venv from requirements.txt)"
python3 "$REPO/dev/mock_endpoint.py" "$PORT" >/dev/null 2>&1 & MOCK=$!; sleep 1
LIM=(--limit 5); [ "$FULL" = 1 ] && LIM=()
t0=$(date +%s)
BRINE_URL="http://127.0.0.1:$PORT/v1" BRINE_MODEL=mock BRINE_API_KEY=mock ./run.sh corpus/ "$TMP/out" --no-cache --concurrency 8 "${LIM[@]}" > "$TMP/run.log" 2>&1; rc=$?
[ "$rc" -eq 0 ] && ok "run.sh exit 0 in $(( $(date +%s) - t0 )) s" || { bad "run.sh exit $rc"; tail -15 "$TMP/run.log"; }
for f in camo_graph.yaml camo_graph.json; do [ -s "$TMP/out/$f" ] && ok "$f written" || bad "$f missing"; done
if [ -s "$TMP/out/camo_graph.json" ]; then
  .venv/bin/python - "$TMP/out/camo_graph.json" corpus/index.csv <<'PY' && ok "every index.csv row has a source_documents entry; every edge cites one" || bad "source_documents check failed"
import csv, json, sys
g = json.load(open(sys.argv[1])); rows = list(csv.DictReader(open(sys.argv[2], encoding="utf-8")))
ids = {d["document_id"] for d in g["source_documents"]}
assert len(g["source_documents"]) == len(rows), (len(g["source_documents"]), len(rows))
assert all(e["source_document"] in ids for e in g["edges"]), "edge cites an unknown document"
assert g["edges"], "no edges"
PY
  grep -q "validation: JSON Schema + linkml-validate" "$TMP/run.log" && ok "JSON Schema + linkml-validate passed inside the run" || warn "linkml-validate did not run inside run.sh (check the log)"
fi

echo "-- unit tests (in the clean checkout)"
.venv/bin/python -m pip install -q -r requirements-dev.txt >/dev/null 2>&1
.venv/bin/python -m pytest -q tests > "$TMP/tests.log" 2>&1 && ok "$(tail -1 "$TMP/tests.log")" || { bad "tests: $(tail -1 "$TMP/tests.log")"; }

echo
[ "$FAIL" = 0 ] && echo "PREFLIGHT PASSED for $SHA" || echo "PREFLIGHT FAILED"
exit "$FAIL"
