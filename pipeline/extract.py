"""Stage 3: LLM extraction.  OpenAI-compatible chat client (stdlib only), prompt assembly, chunking, cache, usage.

    python -m pipeline.extract --doc 4CB9X9XE [--prompt system.txt] [--thinking off] [--no-cache]     (one paper, raw output)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .parse import Claim, check_sentences, parse_text

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = Path(__file__).resolve().parent / "prompt"
CACHE_DIR = ROOT / ".cache" / "extract"
DEFAULT_PROMPT = "system.txt"
CHARS_PER_TOKEN = 3.5

REPAIR_INSTRUCTION = ("The lines below do not follow the output format. Rewrite each one in the format. "
                      "Output only the corrected lines, nothing else.\n\n")


class LLMError(RuntimeError):
    pass


class ConfigError(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------- config / prompt
@dataclass
class LLMConfig:
    url: str
    model: str
    key: str = field(repr=False)                     # never printed
    thinking: bool = False
    max_tokens: int = 3000
    idle_timeout: float = 120.0        # no bytes from the server for this long -> the attempt fails (and is retried)
    total_timeout: float = 1200.0      # one attempt may take at most this long, however steadily it streams
    retries: int = 3
    use_cache: bool = True
    refresh_cache: bool = False        # ignore cached answers but store the new ones (repeat runs that still leave a cache)
    cache_salt: str = ""               # appended to the cache key when set (own entries, e.g. the under-extraction retry)
    cache_dir: Path = CACHE_DIR


def config_from_env(thinking: bool = False, use_cache: bool = True, max_tokens: int = 3000) -> LLMConfig:
    names = ("BRINE_URL", "BRINE_MODEL", "BRINE_API_KEY")
    missing = [n for n in names if not os.environ.get(n, "").strip()]
    if missing:
        raise ConfigError("missing environment variable(s): " + ", ".join(missing) +
                          ". Set BRINE_URL (endpoint), BRINE_MODEL (model name) and BRINE_API_KEY (key).")
    return LLMConfig(url=os.environ["BRINE_URL"].strip().rstrip("/"), model=os.environ["BRINE_MODEL"].strip(),
                     key=os.environ["BRINE_API_KEY"].strip(), thinking=thinking, use_cache=use_cache, max_tokens=max_tokens)


def available_prompts() -> List[str]:
    return sorted(p.name for p in PROMPT_DIR.glob("*.txt"))


def load_prompt(name: str = DEFAULT_PROMPT) -> Tuple[str, str]:
    """Return (filename, text) of a prompt file in pipeline/prompt/.  Plain file names only."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ConfigError(f"--prompt takes a file name from {PROMPT_DIR.name}/, not a path: {name!r} (available: {', '.join(available_prompts())})")
    for cand in (name, name + ".txt"):
        p = PROMPT_DIR / cand
        if p.is_file():
            return p.name, p.read_text(encoding="utf-8")
    raise ConfigError(f"no prompt {name!r} in pipeline/prompt/ (available: {', '.join(available_prompts())})")


# ----------------------------------------------------------------------------------------------- client
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def strip_thinking(text: str) -> str:
    text = _THINK.sub("", text or "")
    if re.match(r"\s*<think>", text, re.I):               # opened but never closed: the whole reply was thinking
        return ""
    return re.sub(r"</?think>", "", text, flags=re.I).strip()


@dataclass
class Result:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    cached: bool = False
    thinking_mode: str = "off"            # off (kwargs) | off (/no_think) | on
    think_returned: bool = False          # did the reply contain a <think> block (before it was stripped)?
    raw: str = ""                         # the reply exactly as the endpoint sent it
    finish_reason: Optional[str] = None   # 'length' = cut off at max_tokens (inferred from the token count for old cache entries)


class Client:
    RETRY_HEADER = ["timestamp", "doc", "attempt", "error", "sleep_s", "gave_up"]

    def __init__(self, cfg: LLMConfig, sleep: Callable[[float], None] = time.sleep,
                 post: Optional[Callable[[str, dict], Tuple[int, dict]]] = None, retry_log: Optional[Path] = None):
        self.cfg = cfg
        self._sleep = sleep
        self._post_fn = post or self._http_post
        self._chat_url: Optional[str] = None
        self._kwargs_rejected = False
        self._stream = "full"                  # full (stream + usage) -> nousage -> off, if the server objects
        self.modes_seen: Dict[str, int] = {}
        self._retry_log = Path(retry_log) if retry_log else None
        self._lock = threading.Lock()
        self._tl = threading.local()

    # --- retry log ---
    def init_retry_log(self) -> None:
        """Create output/retries.csv (header only) so the file exists even when nothing needed a retry."""
        if self._retry_log:
            with self._lock:
                self._retry_log.parent.mkdir(parents=True, exist_ok=True)
                if not self._retry_log.exists():
                    with open(self._retry_log, "w", encoding="utf-8", newline="") as f:
                        csv.writer(f).writerow(self.RETRY_HEADER)

    def _log_retry(self, attempt: int, error: str, sleep_s: float, gave_up: bool) -> None:
        label = getattr(self._tl, "label", "")
        log.warning("%s: attempt %d failed (%s)%s", label or "-", attempt, error, "; giving up" if gave_up else f"; retrying in {sleep_s:g}s")
        if not self._retry_log:
            return
        with self._lock:
            new = not self._retry_log.exists()
            self._retry_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._retry_log, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(self.RETRY_HEADER)
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), label, attempt, error[:200], f"{sleep_s:g}", int(gave_up)])

    # --- transport (the only place that touches the key) ---
    def _http_post(self, url: str, payload: dict) -> Tuple[int, dict]:
        """Streamed request.  Degrades to 'stream without usage', then to a plain request, if the server rejects the stream options."""
        while True:
            body = dict(payload)
            if self._stream != "off":
                body["stream"] = True
                if self._stream == "full":
                    body["stream_options"] = {"include_usage": True}
            status, data = self._post_once(url, body)
            if status in (400, 422) and self._stream != "off" and "stream" in json.dumps(data).lower():
                self._stream = "nousage" if self._stream == "full" else "off"
                log.warning("server rejected the stream options; falling back to stream mode %r", self._stream)
                continue
            return status, data

    def _post_once(self, url: str, payload: dict) -> Tuple[int, dict]:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.cfg.key}", "User-Agent": "evidencejam-pipeline/1.0",
            "Accept": "text/event-stream, application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=self.cfg.idle_timeout)    # the socket timeout is the idle timeout
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                body = {"error": {"message": f"HTTP {e.code}"}}
            return e.code, body
        with r:
            if "text/event-stream" not in (r.headers.get("Content-Type") or ""):
                return r.status, json.loads(r.read().decode("utf-8"))      # server ignored stream=true: a normal JSON reply
            t0 = time.monotonic()
            parts: List[str] = []
            usage: dict = {}
            finish: Optional[str] = None
            first: Optional[float] = None
            while True:
                if time.monotonic() - t0 > self.cfg.total_timeout:
                    raise TimeoutError(f"total timeout: more than {self.cfg.total_timeout:g}s for one response")
                line = r.readline()                                          # raises on an idle timeout
                if not line:
                    break
                s = line.decode("utf-8", "replace").strip()
                if not s.startswith("data:"):
                    continue                                                 # blank lines and ': keep-alive' comments
                data = s[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if obj.get("error") and not obj.get("choices"):
                    raise ConnectionError("stream error: " + str(obj["error"])[:150])
                if obj.get("usage"):
                    usage = obj["usage"]
                for ch in obj.get("choices") or []:
                    finish = ch.get("finish_reason") or finish
                    c = (ch.get("delta") or {}).get("content")
                    if c:
                        if first is None:
                            first = time.monotonic() - t0
                            log.info("%s: first token after %.1fs", getattr(self._tl, "label", "") or "-", first)
                        parts.append(c)
            if not parts and not usage:
                raise ConnectionError("empty stream (no content, no usage)")
            return 200, {"choices": [{"message": {"content": "".join(parts)}, "finish_reason": finish}], "usage": usage}

    def _detect_url(self) -> str:
        if self._chat_url:
            return self._chat_url
        base = re.sub(r"/chat/completions$", "", self.cfg.url)
        self._chat_url = base + "/chat/completions"
        return self._chat_url

    def _call(self, payload: dict) -> Tuple[int, dict]:
        """POST with retries on network errors, 5xx and 429; one-off URL detection on a 404."""
        last = "no attempt"
        for attempt in range(self.cfg.retries + 1):
            url = self._detect_url()
            try:
                status, body = self._post_fn(url, payload)
            except Exception as e:  # noqa: BLE001  (network error, timeout, bad JSON)
                last = f"{type(e).__name__}: {str(e)[:100]}"
                status, body = None, {}
            if status == 404 and not url.endswith("/v1/chat/completions") and "/v1" not in url:
                base = re.sub(r"/chat/completions$", "", url)
                self._chat_url = base + "/v1/chat/completions"
                continue
            if status is not None and status < 500 and status != 429:
                return status, body
            if status is not None:
                last = f"HTTP {status}"
            last_attempt = attempt >= self.cfg.retries
            wait = 0 if last_attempt else 2 ** (attempt + 1)
            self._log_retry(attempt + 1, last, wait, last_attempt)
            if not last_attempt:
                self._sleep(wait)
        raise LLMError(f"request failed after {self.cfg.retries + 1} attempts ({last})")

    # --- one completion ---
    def _cache_path(self, system: str, user: str, thinking: bool) -> Path:
        key = [self.cfg.model, system, user, thinking, self.cfg.max_tokens]
        if getattr(self.cfg, "cache_salt", ""):
            key.append(self.cfg.cache_salt)        # e.g. the under-extraction retry: its own entry; unset = old keys
        h = hashlib.sha256(json.dumps(key).encode("utf-8")).hexdigest()
        return self.cfg.cache_dir / f"{h}.json"

    def complete(self, system: str, user: str, label: str = "") -> Result:
        self._tl.label = label
        thinking = self.cfg.thinking
        cp = self._cache_path(system, user, thinking)
        if self.cfg.use_cache and not self.cfg.refresh_cache and cp.exists():
            try:
                d = json.loads(cp.read_text(encoding="utf-8"))
                return Result(d["text"], d["prompt_tokens"], d["completion_tokens"], d.get("seconds", 0.0), True, d.get("mode", "off"),
                              bool(d.get("think", False)), d.get("raw", d["text"]),
                              d.get("finish") or self._inferred_finish(d["completion_tokens"]))
            except Exception:  # noqa: BLE001
                pass
        t0 = time.time()
        mode = "on"
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        payload: dict = {"model": self.cfg.model, "messages": msgs, "temperature": 0, "max_tokens": self.cfg.max_tokens}
        if not thinking:
            if not self._kwargs_rejected:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
                mode = "off (kwargs)"
            else:
                msgs[1] = {"role": "user", "content": "/no_think\n" + user}
                mode = "off (/no_think)"
        status, body = self._call(payload)
        if status in (400, 422) and "chat_template_kwargs" in payload:
            self._kwargs_rejected = True
            payload.pop("chat_template_kwargs")
            payload["messages"] = [msgs[0], {"role": "user", "content": "/no_think\n" + user}]
            mode = "off (/no_think)"
            status, body = self._call(payload)
        if status != 200:
            msg = (body.get("error") or {}).get("message") if isinstance(body, dict) else None
            raise LLMError(f"HTTP {status}: {str(msg)[:200]}")
        try:
            text = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("unexpected response shape (no choices[0].message.content)")
        usage = body.get("usage") or {}
        try:
            finish = body["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError):
            finish = None
        pt = int(usage.get("prompt_tokens") or (len(system) + len(user)) / CHARS_PER_TOKEN)
        ct = int(usage.get("completion_tokens") or len(text) / CHARS_PER_TOKEN)
        raw_reply, had_think = text, bool(re.search(r"<think>", text, re.I))
        text = strip_thinking(text)
        secs = time.time() - t0
        log.info("%s: done, %d prompt + %d completion tokens in %.0fs (%.1f tok/s)", label or "-", pt, ct, secs, ct / secs if secs else 0.0)
        self.modes_seen[mode] = self.modes_seen.get(mode, 0) + 1
        if self.cfg.use_cache:
            try:
                cp.parent.mkdir(parents=True, exist_ok=True)
                tmp = cp.with_name(f"{cp.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_text(json.dumps({"text": text, "prompt_tokens": pt, "completion_tokens": ct, "seconds": secs, "mode": mode,
                                          "think": had_think, "raw": raw_reply, "finish": finish or self._inferred_finish(ct)}),
                               encoding="utf-8")
                os.replace(tmp, cp)       # atomic: parallel jobs never read a half-written entry
            except OSError:
                pass
        return Result(text, pt, ct, secs, False, mode, had_think, raw_reply, finish or self._inferred_finish(ct))

    def _inferred_finish(self, completion_tokens: int) -> Optional[str]:
        return "length" if completion_tokens >= self.cfg.max_tokens else None


# ----------------------------------------------------------------------------------------------- chunking
_SENT_LINE = re.compile(r"^\[(\d+)\] \((\w+)\) ")


def split_user_text(user: str, max_input_tokens: int = 12000) -> List[str]:
    """One chunk if the text fits; otherwise split at section boundaries.  Each chunk repeats TITLE/SPECIES/CONTEXT and keeps
    the original sentence numbers."""
    if len(user) / CHARS_PER_TOKEN <= max_input_tokens:
        return [user]
    lines = user.splitlines()
    try:
        i = lines.index("TEXT:")
    except ValueError:
        return [user]
    header = "\n".join(lines[: i + 1]) + "\n"
    body = [ln for ln in lines[i + 1:] if ln.strip()]
    budget = max(2000, int(max_input_tokens * CHARS_PER_TOKEN) - len(header))
    runs: List[List[str]] = []
    cur_sec = None
    for ln in body:
        m = _SENT_LINE.match(ln)
        sec = m.group(2) if m else cur_sec
        if sec != cur_sec or not runs:
            runs.append([])
            cur_sec = sec
        runs[-1].append(ln)
    chunks: List[List[str]] = []
    cur: List[str] = []
    size = 0
    for run in runs:
        rsize = sum(len(x) + 1 for x in run)
        if cur and size + rsize > budget:
            chunks.append(cur)
            cur, size = [], 0
        if rsize > budget:                               # a single section is too long: split it by sentences
            for ln in run:
                if cur and size + len(ln) + 1 > budget:
                    chunks.append(cur)
                    cur, size = [], 0
                cur.append(ln)
                size += len(ln) + 1
        else:
            cur.extend(run)
            size += rsize
    if cur:
        chunks.append(cur)
    return [header + "\n".join(c) + "\n" for c in chunks]


# ----------------------------------------------------------------------------------------------- one paper
@dataclass
class Extraction:
    claims: List[Claim]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    chunks: int = 0
    n_bad: int = 0
    n_repaired: int = 0
    n_dropped_lines: int = 0
    n_dropped_sentences: int = 0
    raw: List[str] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)
    n_truncated: int = 0                  # calls cut off at max_tokens (always counted)
    n_continued: int = 0                  # continuation calls made (--continue-truncated)
    n_glean_calls: int = 0                # gleaning calls made (--glean)
    n_gleaned: int = 0                    # claims they added


def continuation_input(chunk: str, claims: Sequence[Claim]) -> Optional[str]:
    """The chunk again, with only the sentences after the last one the cut-off reply cited (camo_pipeline run.py
    `truncated_rest`).  None when nothing is left, or when the chunk has no numbered sentences."""
    if "TEXT:\n" not in chunk:
        return None
    head, body = chunk.split("TEXT:\n", 1)
    lines = [ln for ln in body.splitlines() if _SENT_LINE.match(ln)]
    if not lines:
        return None
    last = max((n for c in claims for n in c.sentences), default=0)
    rest = [ln for ln in lines if int(_SENT_LINE.match(ln).group(1)) > last]
    if not rest or len(rest) == len(lines):          # nothing left, or no progress (the same input would give the same reply)
        return None
    return head + "TEXT:\n" + "\n".join(rest) + "\n"


def extract_paper(client: Client, system: str, user_text: str, valid_numbers: Sequence[int], max_input_tokens: int = 12000,
                  label: str = "", chunks: Optional[List[str]] = None, continue_truncated: bool = False) -> Extraction:
    """`chunks`: ready-made per-call inputs (e.g. one per paragraph chunk); otherwise the text is split only when too long."""
    ex = Extraction([])
    claims: List[Claim] = []
    bad: List[str] = []
    todo = [(c, 0) for c in (chunks or split_user_text(user_text, max_input_tokens))]
    while todo:
        chunk, depth = todo.pop(0)
        r = client.complete(system, chunk, label)
        ex.chunks += 1
        ex.prompt_tokens += r.prompt_tokens
        ex.completion_tokens += r.completion_tokens
        ex.seconds += r.seconds
        ex.raw.append(r.text)
        ex.modes.append(r.thinking_mode)
        c, b = parse_text(r.text)
        claims += c
        bad += b
        if r.finish_reason == "length":
            ex.n_truncated += 1
            if continue_truncated and b and r.text.rstrip().endswith(b[-1]):
                bad.pop()                                # the last line was cut mid-way: re-read below, not repaired
            nxt = continuation_input(chunk, c) if continue_truncated and depth < 2 else None
            if nxt:                                      # --continue-truncated: the unread rest of this chunk, at most twice
                ex.n_continued += 1
                todo.insert(0, (nxt, depth + 1))
    ex.n_bad = len(bad)
    if bad:                                              # one repair call with only the broken lines
        try:
            r = client.complete(system, REPAIR_INSTRUCTION + "\n".join(bad), label)
            ex.prompt_tokens += r.prompt_tokens
            ex.completion_tokens += r.completion_tokens
            ex.seconds += r.seconds
            ex.raw.append(r.text)
            c, b2 = parse_text(r.text)
            claims += c
            ex.n_repaired = len(c)
            ex.n_dropped_lines = len(b2) + max(0, len(bad) - len(c) - len(b2))
        except LLMError as e:
            log.warning("repair call failed (%s); dropping %d lines", e, len(bad))
            ex.n_dropped_lines = len(bad)
    claims, dropped = check_sentences(claims, valid_numbers)
    ex.n_dropped_sentences = dropped
    ex.claims = claims
    return ex


# ----------------------------------------------------------------------------------------------- gleaning (--glean)
GLEAN_SECTIONS = {"abs", "res", "dis", "con"}
GLEAN_MIN = 3                    # auto: at least this many candidate sentences, else no call
GLEAN_MAX_CHARS = 8000           # ~2,300 input tokens of candidate sentences per paper: with --study and --ontology select the
                                 # add-ons stay inside +30 % of the submitted 10.6k tokens per paper (header ~700 tokens extra)
_RESULT_CUE = re.compile(r"\[sig\]|\[ns\]|\b(?:increas|decreas|reduc|higher|lower|greater|fewer|affect|effect|differ|"
                         r"associat|correlat|depend|influenc|improv|suppress|enhanc|declin)\w*|\bno significant\b|\bdid not\b",
                         re.I)


def glean_candidates(sentences: Sequence[dict], claims: Sequence[Claim], mode: str = "auto") -> List[dict]:
    """Sentences worth a second look (camo_pipeline run.glean_candidates): in abstract / results / discussion / conclusions,
    cited by no claim, and (auto) with a significance token or a result word.  [] when auto finds fewer than GLEAN_MIN."""
    cited = {n for c in claims for n in c.sentences}
    out = [s for s in sentences if s.get("section") in GLEAN_SECTIONS and int(s["n"]) not in cited
           and (mode == "always" or _RESULT_CUE.search(s.get("compressed") or ""))]
    if mode == "auto" and len(out) < GLEAN_MIN:
        return []
    kept, size = [], 0
    for s in out:
        size += len(s.get("compressed") or "") + 12
        if size > GLEAN_MAX_CHARS:
            break
        kept.append(s)
    return kept


def glean(client: Client, system: str, user_text: str, sentences: Sequence[dict], ex: Extraction, valid_numbers: Sequence[int],
          mode: str = "auto", label: str = "") -> int:
    """One extra call over the candidate sentences, in the normal input format (same header, original numbers), so the
    prompt, parser and cache are unchanged.  New claims are added to `ex`; returns how many."""
    cands = glean_candidates(sentences, ex.claims, mode)
    if not cands or "TEXT:\n" not in user_text:
        return 0
    head = user_text.split("TEXT:\n", 1)[0]
    text = head + "TEXT:\n" + "\n".join(f"[{s['n']}] ({s['section']}) {s['compressed']}" for s in cands) + "\n"
    try:
        r = client.complete(system, text, label)
    except LLMError as e:
        log.warning("%s: gleaning call failed (%s)", label or "-", e)
        return 0
    ex.prompt_tokens += r.prompt_tokens
    ex.completion_tokens += r.completion_tokens
    ex.seconds += r.seconds
    ex.raw.append(r.text)
    ex.n_glean_calls += 1
    new, _bad = parse_text(r.text)
    new, _ = check_sentences(new, [int(s["n"]) for s in cands])      # only claims about the sentences that were sent
    ex.claims += new
    ex.n_gleaned += len(new)
    return len(new)


# ----------------------------------------------------------------------------------------------- CLI: one paper
def main(argv: Optional[List[str]] = None) -> int:
    from .preprocess.assemble import Options, process_paper
    from .preprocess.legend import load_taxon_table
    from .preprocess.tokens import get_counter

    ap = argparse.ArgumentParser(prog="pipeline.extract", description="Run the LLM extraction on one paper and print the raw lines.")
    ap.add_argument("--doc", required=True, help="slug, e.g. 4CB9X9XE")
    ap.add_argument("--corpus", default=str(ROOT / "corpus"))
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="file in pipeline/prompt/ (default system.txt)")
    ap.add_argument("--thinking", choices=("on", "off"), default="off")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--max-input-tokens", type=int, default=12000)
    ap.add_argument("--max-tokens", type=int, default=3000)
    a = ap.parse_args(argv)
    try:
        pname, system = load_prompt(a.prompt)
        cfg = config_from_env(a.thinking == "on", not a.no_cache, a.max_tokens)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    corpus = Path(a.corpus)
    meta = {}
    with open(corpus / "index.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["slug"] == a.doc:
                meta = row
    raw = (corpus / f"{a.doc}.md").read_text(encoding="utf-8", errors="replace")
    count, _ = get_counter(allow_download=False)
    pre = process_paper(a.doc, raw, meta, count, Options(), load_taxon_table())
    client = Client(cfg)
    valid = [s["n"] for s in pre.sidecar["sentences"]]
    ex = extract_paper(client, system, pre.txt, valid, a.max_input_tokens, a.doc)
    print(f"# prompt={pname} thinking={a.thinking} mode(s)={sorted(set(ex.modes))}")
    print("\n".join(ex.raw))
    tps = ex.completion_tokens / ex.seconds if ex.seconds else float("nan")
    print(f"# prompt_tokens={ex.prompt_tokens} completion_tokens={ex.completion_tokens} seconds={ex.seconds:.1f} "
          f"completion_tokens_per_second={tps:.1f} chunks={ex.chunks} parsed={len(ex.claims)} bad_lines={ex.n_bad}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
