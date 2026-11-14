"""The teammate's preprocessing, adapted: offsets map to the raw file, numbering is 1..n, header comes from our stage 1."""
import csv
from pathlib import Path

from pipeline.main import get_preprocessor
from pipeline.preprocess.assemble import Options
from pipeline.preprocess.legend import load_taxon_table
from pipeline.preprocess.tokens import get_counter
from pipeline.extract import ConfigError
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(slug):
    meta = next(r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8")) if r["slug"] == slug)
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace")
    count, _ = get_counter(allow_download=False)
    return raw, get_preprocessor("paragraph")(slug, raw, meta, count, Options(), load_taxon_table())


def test_team_sentences_map_to_raw_offsets():
    raw, pre = _run("4CB9X9XE")
    sents = pre.sidecar["sentences"]
    assert [s["n"] for s in sents] == list(range(1, len(sents) + 1))
    for s in sents:
        assert raw[s["start_char"]:s["end_char"]] == s["raw"] and s["end_char"] > s["start_char"]
    assert pre.txt.startswith("TITLE:") and "\nSPECIES:" in pre.txt and "\nTEXT:\n[1] (" in pre.txt


def test_unknown_preprocessor_is_a_config_error():
    with pytest.raises(ConfigError):
        get_preprocessor("nope")


def test_paragraph_chunks_same_sentences_split_into_calls():
    meta = next(r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8")) if r["slug"] == "YKQQZV93")
    raw = (ROOT / "corpus/YKQQZV93.md").read_text(encoding="utf-8", errors="replace")
    count, _ = get_counter(allow_download=False)
    one = get_preprocessor("paragraph")("YKQQZV93", raw, meta, count, Options(), load_taxon_table())
    many = get_preprocessor("paragraph-chunks")("YKQQZV93", raw, meta, count, Options(), load_taxon_table())
    assert [s["clean"] for s in one.sidecar["sentences"]] == [s["clean"] for s in many.sidecar["sentences"]]
    texts = many.sidecar["chunk_texts"]
    assert len(texts) >= 2 and all(t.startswith("TITLE:") and "\nTEXT:\n[" in t for t in texts)
    assert sum(t.count("\n[") for t in texts) == len(many.sidecar["sentences"])
    assert "chunk_texts" not in one.sidecar
