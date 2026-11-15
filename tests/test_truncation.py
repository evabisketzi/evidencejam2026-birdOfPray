"""--continue-truncated and finish_reason tracking (pipeline/extract.py)."""
import json
import re

from pipeline.extract import Client, LLMConfig, continuation_input, extract_paper
from pipeline.parse import parse_text

HEAD = "TITLE: t\nSPECIES: T1=Alliaria petiolata\nCONTEXT: c\nTEXT:\n"
CHUNK = HEAD + "\n".join(f"[{n}] (res) Sentence {n} density was lower." for n in range(1, 11)) + "\n"


def _cfg(tmp_path, **kw):
    return LLMConfig(url="http://h/v1", model="m", key="k", cache_dir=tmp_path, max_tokens=100, **kw)


def _post_factory(calls):
    """First call: cites sentences 1-4 then is cut off mid-line (finish_reason length).  Later calls: one line per sentence."""
    def post(url, payload):
        user = payload["messages"][1]["content"]
        calls.append(user)
        nums = [int(n) for n in re.findall(r"^\[(\d+)\] ", user, re.M)]
        if len(calls) == 1:
            text = "\n".join(f"F|{n}|T1/density/+|c|plant community/cover/-|D|exp" for n in nums[:4]) + "\nF|5|T1/dens"
            return 200, {"choices": [{"message": {"content": text}, "finish_reason": "length"}],
                         "usage": {"prompt_tokens": 50, "completion_tokens": 100}}
        text = "\n".join(f"F|{n}|T1/density/+|c|plant community/cover/-|D|exp" for n in nums)
        return 200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 30, "completion_tokens": 20}}
    return post


def test_continuation_input_keeps_header_and_only_unread_sentences():
    claims, _ = parse_text("F|1|T1/density/+|c|x/cover/-|D|exp\nF|3-4|T1/density/+|c|x/cover/-|D|exp")
    nxt = continuation_input(CHUNK, claims)
    assert nxt.startswith(HEAD) and "[5] (res)" in nxt and "[4] (res)" not in nxt and nxt.count("\n[") == 6
    assert continuation_input(CHUNK, []) is None                     # no progress: the same input would give the same reply
    done, _ = parse_text("F|10|T1/density/+|c|x/cover/-|D|exp")
    assert continuation_input(CHUNK, done) is None                    # nothing left
    assert continuation_input("no text block", claims) is None


def test_cut_off_reply_is_continued_and_the_broken_line_is_not_repaired(tmp_path):
    calls = []
    c = Client(_cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=_post_factory(calls))
    ex = extract_paper(c, "sys", CHUNK, list(range(1, 11)), chunks=[CHUNK], continue_truncated=True)
    assert sorted({n for cl in ex.claims for n in cl.sentences}) == list(range(1, 11))
    assert (ex.n_truncated, ex.n_continued, ex.chunks, ex.n_bad) == (1, 1, 2, 0)
    assert "[4] (res)" not in calls[1] and "[5] (res)" in calls[1]
    assert ex.prompt_tokens == 80 and ex.completion_tokens == 120


def test_flag_off_counts_the_cut_off_but_changes_nothing_else(tmp_path):
    calls = []
    c = Client(_cfg(tmp_path, use_cache=False), sleep=lambda s: None, post=_post_factory(calls))
    ex = extract_paper(c, "sys", CHUNK, list(range(1, 11)), chunks=[CHUNK])
    assert ex.n_truncated == 1 and ex.n_continued == 0
    assert sorted({n for cl in ex.claims for n in cl.sentences}) == [1, 2, 3, 4]
    assert ex.n_bad == 1                                              # the cut line still goes to the usual repair call
    assert len(calls) == 2 and calls[1].startswith("The lines below do not follow") and calls[1].endswith("F|5|T1/dens")


def test_finish_reason_is_cached_and_inferred_for_old_entries(tmp_path):
    calls = []
    c = Client(_cfg(tmp_path), sleep=lambda s: None, post=_post_factory(calls))
    assert c.complete("sys", CHUNK).finish_reason == "length"
    entry = next(tmp_path.glob("*.json"))
    d = json.loads(entry.read_text(encoding="utf-8"))
    assert d["finish"] == "length"
    del d["finish"]                                                   # a cache entry written before this change
    entry.write_text(json.dumps(d), encoding="utf-8")
    r = c.complete("sys", CHUNK)
    assert r.cached and r.finish_reason == "length"                   # completion_tokens (100) reached max_tokens (100)
