#!/usr/bin/env python3
"""SessionStart: a short status block added to Claude's context (branch, uncommitted files, job runner, last experiment,
time left until judging).  Never fails, never prints secrets."""
import datetime as dt
import subprocess
from pathlib import Path

from _common import ROOT

DEADLINE = dt.datetime(2026, 11, 15, 23, 0, tzinfo=dt.timezone.utc)   # Sunday Nov 15, 6 p.m. EST (UTC-5)


def sh(*a: str) -> str:
    try:
        return subprocess.run(list(a), cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


lines = ["## Project status (SessionStart hook)"]
branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
dirty = [l for l in sh("git", "status", "--porcelain").splitlines() if l]
lines.append(f"- git: branch `{branch}`, last commit `{sh('git', 'log', '-1', '--format=%h %s')[:90]}`, {len(dirty)} uncommitted path(s)")
q = sorted(p.name for p in (ROOT / "dev/jobs/queue").glob("*.job")) if (ROOT / "dev/jobs/queue").exists() else []
runner = "running" if "jobs:" in sh("tmux", "ls") else "not running"
lines.append(f"- endpoint job runner (tmux `jobs`): {runner}; queued: {', '.join(q) or 'none'}")
rl = ROOT / "dev/jobs/runner.log"
if rl.exists():
    last = rl.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
    if last:
        lines.append(f"- last runner event: {last[0]}")
log = ROOT / "dev/experiments/LOG.md"
if log.exists():
    heads = [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("## ")]
    if heads:
        lines.append(f"- last experiment: {heads[-1][3:]}")
left = DEADLINE - dt.datetime.now(dt.timezone.utc)
if left.total_seconds() > 0:
    lines.append(f"- judging snapshot (last commit before Sun Nov 15, 6 p.m. EST) in {left.days} d {left.seconds // 3600} h")
else:
    lines.append("- judging deadline has passed")
print("\n".join(lines))
