#!/usr/bin/env python3
"""PreToolUse (Bash|Edit|Write|MultiEdit): keep the endpoint key out of the repository.

* git commit  -> scans the staged diff (and, for `commit -a`, the unstaged diff of tracked files)
* git push    -> scans every commit that would be pushed
* Edit/Write  -> scans the new file content
Blocks with exit code 2 if a key-like string (sk-…, BRINE_API_KEY=<literal>, Bearer <token>) or the exact value of
BRINE_API_KEY (when set in this environment) appears.  The key is never printed, only a redacted hint.
"""
import re
import subprocess

from _common import ROOT, block, find_secrets, read_event, rel

ev = read_event()
tool = ev.get("tool_name", "")
ti = ev.get("tool_input") or {}


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return ""


def added_lines(diff: str) -> str:
    return "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))


if tool == "Bash":
    cmd = ti.get("command", "")
    texts = []
    if re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd):
        texts.append(("staged changes", added_lines(git("diff", "--cached", "-U0"))))
        if re.search(r"\bcommit\b[^|;&]*\s-[a-zA-Z]*a", cmd):
            texts.append(("tracked changes (commit -a)", added_lines(git("diff", "-U0"))))
    if re.search(r"\bgit\b[^|;&]*\bpush\b", cmd):
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
        rng = f"{upstream}..HEAD" if upstream else "HEAD"
        # commits not on any remote yet (falls back to the last 50 commits when there is no upstream)
        outgoing = git("log", "-p", "--format=%H", rng, "--not", "--remotes") if upstream else git("log", "-p", "-50", "--format=%H", "HEAD", "--not", "--remotes")
        texts.append(("commits to be pushed", added_lines(outgoing)))
    for where, text in texts:
        hits = find_secrets(text)
        if hits:
            block(f"Blocked: {where} contain {hits[0]}{' and more' if len(hits) > 1 else ''}. The endpoint key must only come "
                  f"from the environment (BRINE_API_KEY); remove it from the files (and from history if already committed) first.")

elif tool in ("Edit", "Write", "MultiEdit"):
    content = ti.get("content") or ti.get("new_string") or ""
    for e in ti.get("edits") or []:
        content += "\n" + (e.get("new_string") or "")
    hits = find_secrets(content)
    if hits:
        block(f"Blocked: the new content for {rel(ti.get('file_path')) or ti.get('file_path')} contains {hits[0]}. "
              f"Never write the API key into a file; code reads BRINE_API_KEY from the environment.")
