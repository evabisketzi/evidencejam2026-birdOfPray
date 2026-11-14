"""Token counting with the Qwen tokenizer (falls back gracefully, and says which one).

Resolution order:
  1. ``PREPROCESS_TOKENIZER`` env var -> path to a ``tokenizer.json`` (needs ``tokenizers``)
  2. cached ``.cache/qwen3_tokenizer.json``; downloaded from Hugging Face if missing (needs ``tokenizers``)
  3. ``transformers.AutoTokenizer`` for a Qwen3 model
  4. tiktoken built from ``data/qwen.tiktoken`` (if present) with Qwen's pre-tokenizer pattern
  5. digit-aware heuristic estimate (stdlib only; always available)
"""
from __future__ import annotations

import logging
import math
import os
import re
import urllib.request
from pathlib import Path
from typing import Callable, Tuple

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "qwen3_tokenizer.json"
HF_URL = "https://huggingface.co/Qwen/Qwen3-8B/resolve/main/tokenizer.json"
QWEN_PAT = (r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+")

_WORD = re.compile(r"\d|[^\W\d_]+|[^\s\w]|_")


def _heuristic(text: str) -> int:
    """Qwen splits numbers digit by digit; words average ~4.5 chars/token."""
    n = 0
    for m in _WORD.finditer(text):
        t = m.group()
        n += 1 if (t.isdigit() or not t[0].isalpha()) else max(1, math.ceil(len(t) / 4.5))
    return n


def _from_tokenizers(path: Path):
    from tokenizers import Tokenizer  # type: ignore

    tok = Tokenizer.from_file(str(path))
    return lambda s: len(tok.encode(s).ids)


def get_counter(allow_download: bool = True) -> Tuple[Callable[[str], int], str]:
    """Return (count_fn, description of the tokenizer actually used)."""
    env = os.environ.get("PREPROCESS_TOKENIZER")
    candidates = [Path(env)] if env else []
    candidates.append(CACHE)
    for p in candidates:
        if p.exists():
            try:
                return _from_tokenizers(p), f"tokenizers:{p.name} (Qwen3)"
            except Exception as e:  # noqa: BLE001
                log.warning("tokenizer file %s unusable: %r", p, e)
    if allow_download and not env:
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(HF_URL, headers={"User-Agent": "preprocess/0.1"})
            with urllib.request.urlopen(req, timeout=20) as r, open(CACHE, "wb") as f:
                f.write(r.read())
            return _from_tokenizers(CACHE), "tokenizers:qwen3_tokenizer.json (downloaded)"
        except Exception as e:  # noqa: BLE001
            log.warning("could not obtain Qwen tokenizer.json: %r", e)
            try:
                CACHE.unlink()
            except OSError:
                pass
    try:
        from transformers import AutoTokenizer  # type: ignore

        tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
        return (lambda s: len(tok(s)["input_ids"])), "transformers:Qwen/Qwen3-8B"
    except Exception as e:  # noqa: BLE001
        log.info("transformers tokenizer unavailable: %r", e)
    tt = ROOT / "data" / "qwen.tiktoken"
    if tt.exists():
        try:
            import base64
            import tiktoken  # type: ignore

            ranks = {base64.b64decode(a): int(b) for a, b in (ln.split() for ln in tt.read_text().splitlines() if ln)}
            enc = tiktoken.Encoding("qwen", pat_str=QWEN_PAT, mergeable_ranks=ranks, special_tokens={})
            return (lambda s: len(enc.encode(s, disallowed_special=()))), "tiktoken:qwen.tiktoken"
        except Exception as e:  # noqa: BLE001
            log.info("tiktoken unavailable: %r", e)
    return _heuristic, "heuristic (digit-aware estimate; NOT the Qwen tokenizer)"
