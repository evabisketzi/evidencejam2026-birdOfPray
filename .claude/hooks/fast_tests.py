#!/usr/bin/env python3
"""PostToolUse (Edit|Write|MultiEdit): after a change under pipeline/, dev/score/ or tests/, run the matching fast unit tests.

Only the tests for the area that changed run (0.5-10 s), and the slow end-to-end run tests are skipped; run the full suite
(`.venv/bin/python -m pytest -q tests`, ~50 s) before committing.  A failure exits 2 so Claude sees the tail of the output.
"""
import subprocess
import sys

from _common import ROOT, read_event, rel

SLOW = "not (smoke or a_run or failing_paper or every_paper_fails or merge_uses or timeout or retries)"
GROUPS = [   # (path prefix, pytest args)
    ("pipeline/preprocess/team", ["tests/test_team_adapter.py"]),
    ("pipeline/preprocess/", ["tests/test_sections.py", "tests/test_sentences.py", "tests/test_classify.py", "tests/test_stats.py", "tests/test_murphy.py"]),
    ("pipeline/", ["tests/test_pipeline.py", "-k", SLOW]),
    ("dev/score/", ["tests/test_score.py"]),
    ("dev/overnight_report.py", ["tests/test_overnight_report.py"]),
]

ev = read_event()
r = rel((ev.get("tool_input") or {}).get("file_path"))
if not r.endswith(".py"):
    sys.exit(0)
args = None
if r.startswith("tests/test_"):
    args = [r, "-k", SLOW] if r == "tests/test_pipeline.py" else [r]
else:
    for prefix, a in GROUPS:
        if r.startswith(prefix):
            args = a
            break
if not args:
    sys.exit(0)
py = ROOT / ".venv/bin/python"
if not py.exists():
    sys.exit(0)                     # no dev environment yet: nothing to run
p = subprocess.run([str(py), "-m", "pytest", "-q", "-x", "--no-header", *args], cwd=ROOT, capture_output=True, text=True, timeout=170)
if p.returncode not in (0, 5):     # 5 = no tests collected
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-25:])
    print(f"Fast tests FAILED after editing {r} ({' '.join(args)}):\n{tail}", file=sys.stderr)
    sys.exit(2)
