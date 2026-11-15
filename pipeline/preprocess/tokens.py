"""Token counting with the Qwen tokenizer (falls back gracefully, and says which one).

Resolution order:
  1. ``PREPROCESS_TOKENIZER`` env var -> path to a ``tokenizer.json`` (needs ``tokenizers``)
  2. cached ``.cache/qwen3_tokenizer.json``; downloaded from Hugging Face if missing (needs ``tokenizers``)
  3. ``transformers.AutoTokenizer`` for a Qwen3 model
  4. tiktoken built from ``data/qwen.tiktoken`` (if present) with Qwen's pre-tokenizer pattern
  5. ``data/token_counts.json.gz``: Qwen3 counts precomputed for every text the preprocessing counts on this corpus
     (``dev/build_token_counts.py``), so a clean install without ``tokenizers`` packs the paragraph chunks exactly as the
     evaluated runs did; any other text falls back to 6 (checked before 3 and 4)
  6. digit-aware heuristic estimate (stdlib only; always available)
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
    table = load_count_table()
    if table:
        def counted(s: str) -> int:
            n = table.get(count_key(s))
            return n if n is not None else _heuristic(s)
        return counted, f"table:{COUNT_TABLE.name} (Qwen3 counts for this corpus, {len(table):,} texts; heuristic otherwise)"
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


COUNT_TABLE = ROOT / "data" / "token_counts.json.gz"


def count_key(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def load_count_table() -> dict:
    if not COUNT_TABLE.exists():
        return {}
    try:
        import gzip
        import json
        with gzip.open(COUNT_TABLE, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        log.warning("token count table %s unusable: %r", COUNT_TABLE, e)
        return {}
