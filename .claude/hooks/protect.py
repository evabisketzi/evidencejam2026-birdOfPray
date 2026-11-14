#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit|Bash): block changes to dev/gold/, schema/, corpus/ and data/camo.schema.json.

The gold annotations are the yardstick for every experiment, the schema is the organisers' contract (validation must pass
against it unchanged), and the task forbids modifying corpus/.  To change one of them deliberately, a human edits it outside
Claude Code.  Reading them is always allowed.
"""
import re
import shlex

from _common import PROTECTED, block, is_protected, read_event, rel

ev = read_event()
tool = ev.get("tool_name", "")
ti = ev.get("tool_input") or {}

if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    r = rel(ti.get("file_path") or ti.get("notebook_path"))
    if r and is_protected(r):
        block(f"Blocked: {r} is protected ({', '.join(PROTECTED)}). Gold annotations, the schema and the corpus are not "
              f"edited by Claude. If this change is really intended, ask the user to make it by hand.")

elif tool == "Bash":
    cmd = ti.get("command", "")
    # Commands that write: redirections, in-place edits, moves/removals/copies onto a protected path, git checkout/restore of it.
    writers = re.compile(r"(>>?|\bsed\s+-i\b|\bperl\s+-p?i\b|\brm\b|\bmv\b|\bcp\b|\btee\b|\btruncate\b|\bgit\s+(checkout|restore|rm|mv)\b)")
    if writers.search(cmd):
        try:
            tokens = shlex.split(cmd, posix=True)
        except ValueError:
            tokens = cmd.split()
        for i, t in enumerate(tokens):
            r = rel(t.lstrip(">"))
            if r and is_protected(r):
                # cp FROM a protected path (reading it) is fine; anything else that names it while writing is not
                if tokens[i - 1:i] == ["cp"] and i + 1 < len(tokens):
                    continue
                block(f"Blocked: this command would modify {r}, which is protected ({', '.join(PROTECTED)}). "
                      f"Read-only use is fine; changes are made by the user by hand.")
