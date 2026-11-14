"""Shared helpers for the Claude Code hooks in this repo (stdlib only)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root: .claude/hooks/_common.py -> repo

# Paths nobody edits by hand: the human gold annotations, the challenge schema (and the JSON Schema generated from it),
# and the organisers' corpus (the task forbids modifying it).
PROTECTED = ("dev/gold/", "schema/", "corpus/", "data/camo.schema.json")

# What an API key looks like.  The real key is never stored here; when BRINE_API_KEY is set in the hook's environment
# its exact value is checked too.
_KEY_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"BRINE_API_KEY\s*[=:]\s*['\"]?(?!\$|<|\{|your|xxx|\.\.\.)[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bBearer\s+(?!\$|<|\{)[A-Za-z0-9_\-\.]{24,}"),
]


def read_event() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:  # noqa: BLE001 - a hook must never crash the session
        return {}


def rel(path: str | None) -> str:
    """Repo-relative path ('' if outside the repo)."""
    if not path:
        return ""
    p = Path(path)
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return ""


def is_protected(relpath: str) -> bool:
    return any(relpath == p.rstrip("/") or relpath.startswith(p) for p in PROTECTED)


def find_secrets(text: str) -> list[str]:
    """Return short, redacted descriptions of key-like strings found in `text` (never the key itself)."""
    hits = []
    real = os.environ.get("BRINE_API_KEY", "").strip()
    if real and len(real) >= 8 and real in text:
        hits.append("the exact value of BRINE_API_KEY")
    for rx in _KEY_PATTERNS:
        for m in rx.finditer(text):
            s = m.group(0)
            hits.append(f"key-like string '{s[:6]}…' ({len(s)} chars)")
    return hits


def block(msg: str) -> None:
    """Exit code 2 = block the tool call; stderr is shown to Claude."""
    print(msg, file=sys.stderr)
    sys.exit(2)
