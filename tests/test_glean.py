"""--glean: one extra call on result sentences no claim cites (pipeline/extract.py glean)."""
import json
import re
from pathlib import Path

from pipeline.extract import Client, Extraction, LLMConfig, GLEAN_MAX_CHARS, glean, glean_candidates
from pipeline.parse import parse_text

ROOT = Path(__file__).resolve().parent.parent
HEAD = "TITLE: t\nSPECIES: T1=Alliaria petiolata\nCONTEXT: c\nTEXT:\n"


def _sents():
    return [{"n": 1, "section": "res", "compressed": "Density was lower in caged plots [sig]."},
            {"n": 2, "section": "res", "compressed": "Cover did not differ between treatments [ns]."},
            {"n": 3, "section": "met", "compressed": "Plots were sampled monthly [sig]."},          # methods: never
            {"n": 4, "section": "dis", "compressed": "Mowing may reduce seed output."},
            {"n": 5, "section": "res", "compressed": "Plots were 1 m2."},                          # no result word
            {"n": 6, "section": "abs", "compressed": "Survival increased with shade."}]


def test_candidates_skip_cited_methods_and_cue_less_sentences():
    cited, _ = parse_text("F|1|T1/density/+|c|x/cover/-|D|exp")
    assert [s["n"] for s in glean_candidates(_sents(), cited)] == [2, 4, 6]
    assert [s["n"] for s in glean_candidates(_sents(), cited, "always")] == [2, 4, 5, 6]
    few, _ = parse_text("F|1,2,4|T1/density/+|c|x/cover/-|D|exp")
    assert glean_candidates(_sents(), few) == []                          # auto: fewer than 3 -> no call


def test_candidates_are_capped():
    many = [{"n": i, "section": "res", "compressed": "Cover was higher [sig]. " * 40} for i in range(1, 200)]
    kept = glean_candidates(many, [])
    assert 0 < len(kept) < len(many) and sum(len(s["compressed"]) + 12 for s in kept) <= GLEAN_MAX_CHARS


def test_glean_sends_only_candidates_in_the_normal_format_and_keeps_their_claims(tmp_path):
    seen = []

    def post(url, payload):
        user = payload["messages"][1]["content"]
        seen.append(user)
        nums = re.findall(r"^\[(\d+)\] ", user, re.M)
        text = "\n".join(f"F|{n}|T1/density/+|c|x/cover/-|D|exp" for n in nums) + "\nF|3|T1/density/+|c|x/cover/-|D|exp"
        return 200, {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 40, "completion_tokens": 9}}
    c = Client(LLMConfig(url="http://h/v1", model="m", key="k", cache_dir=tmp_path, use_cache=False), sleep=lambda s: None, post=post)
    cited, _ = parse_text("F|1|T1/density/+|c|x/cover/-|D|exp")
    ex = Extraction(list(cited), prompt_tokens=100, completion_tokens=20)
    assert glean(c, "sys", HEAD + "[1] (res) whatever\n", _sents(), ex, list(range(1, 7))) == 3
    assert seen[0].startswith(HEAD) and "[2] (res)" in seen[0] and "[1] (res)" not in seen[0] and "[3] (met)" not in seen[0]
    assert sorted(n for cl in ex.claims for n in cl.sentences) == [1, 2, 4, 6]   # the hallucinated sentence 3 is dropped
    assert (ex.n_glean_calls, ex.n_gleaned, ex.prompt_tokens, ex.completion_tokens) == (1, 3, 140, 29)


def test_whole_run_with_glean_validates(monkeypatch, tmp_path):
    from tests.test_ontology_stage import _patch
    m = _patch(monkeypatch)
    assert m.run(ROOT / "corpus", tmp_path / "o", docs=["YKQQZV93"], concurrency=1, use_cache=False, glean_mode="auto") == 0
    log = json.loads((tmp_path / "o" / "run_log.json").read_text(encoding="utf-8"))
    p = log["papers"][0]
    assert log["glean"] == "auto" and p["counts"]["glean_calls"] == 1 and p["counts"]["gleaned_claims"] > 0
