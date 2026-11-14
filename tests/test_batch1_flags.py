"""Flags added for batch 1 (all default off): --preprocess sentence-chunks, --cite-filter relaxed, --taxon-groups,
--retry-underextraction."""
import csv
from pathlib import Path

import pipeline.main as m
from pipeline.extract import Extraction
from pipeline.preprocess import classify as C
from pipeline.preprocess.assemble import Options, process_paper
from pipeline.preprocess.chunks import process_paper_sentence_chunks, split_body
from pipeline.preprocess.legend import Species, group_entries, load_taxon_table, species_forms
from pipeline.preprocess.tokens import get_counter

ROOT = Path(__file__).resolve().parent.parent


def _paper(slug):
    rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus" / "index.csv", encoding="utf-8"))}
    raw = (ROOT / "corpus" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    return slug, raw, rows[slug]


def test_split_body_keeps_every_line_in_order_and_splits_at_sections():
    lines = [f"[{i}] ({'abs' if i < 4 else 'res' if i < 9 else 'dis'}) word word word word" for i in range(1, 13)]
    count = lambda t: len(t.split())
    chunks = split_body(lines, count, budget=30)
    assert [ln for c in chunks for ln in c] == lines and len(chunks) > 1
    assert all(count("\n".join(c)) <= 30 for c in chunks)
    assert chunks[0] == lines[:3]                       # the abstract stays whole; the next section starts a new chunk


def test_sentence_chunks_shows_exactly_the_sentences_of_the_sentence_mode():
    count, _ = get_counter(allow_download=False)
    table = load_taxon_table()
    slug, raw, row = _paper("YKQQZV93")
    base = process_paper(slug, raw, row, count, Options(), table)
    ch = process_paper_sentence_chunks(slug, raw, row, count, Options(), table)
    assert ch.txt == base.txt and ch.sidecar["sentences"] == base.sidecar["sentences"]
    texts = ch.sidecar["chunk_texts"]
    head = base.txt.split("TEXT:\n", 1)[0]
    assert len(texts) > 1 and all(t.startswith(head + "TEXT:\n") for t in texts)
    body = [ln for t in texts for ln in t.split("TEXT:\n", 1)[1].splitlines() if ln.strip()]
    assert body == [ln for ln in base.txt.split("TEXT:\n", 1)[1].splitlines() if ln.strip()]


def test_cite_filter_relaxed_keeps_own_interpretations_in_the_discussion_only():
    s = "This probably occurred because cryptogams are sensitive to even small amounts of tilling (Smith 2001)."
    bg = "Tilling reduces cryptogam cover in grasslands (Smith 2001)."
    assert not C.classify_sentence(s).keep and not C.classify_sentence(bg).keep          # strict (default): unchanged
    assert C.classify_sentence(s, (), True, "dis").keep
    assert not C.classify_sentence(s, (), True, "res").keep
    assert not C.classify_sentence(bg, (), True, "dis").keep


def test_taxon_groups_add_a_legend_entry_with_the_group_id():
    text = "Rodent density declined. Rodents ate the seeds of the willow. Grass cover increased once."
    legend = [Species("Salix bebbiana", ["willow"], 1)]
    got = group_entries(text + " The willow grew.", legend)
    assert [(g.name, g.variants, g.taxid, g.group) for g in got] == [("rodents", ["rodent"], 9989, True)]   # grass: once; willow: taken
    assert species_forms(legend + got) == ["Salix bebbiana"]                # a group word is never an own-study cue
    count, _ = get_counter(allow_download=False)
    slug, raw, row = _paper("4CB9X9XE")
    off = process_paper(slug, raw, row, count, Options(), load_taxon_table())
    on = process_paper(slug, raw, row, count, Options(taxon_groups=True), load_taxon_table())
    assert on.sidecar["sentences"] == off.sidecar["sentences"]
    assert on.sidecar["species"][:len(off.sidecar["species"])] == off.sidecar["species"]
    assert "NCBITaxon:9989" in [sp["ncbitaxon"] for sp in on.sidecar["species"]]


def test_underextraction_retry_keeps_the_answer_with_more_claims(monkeypatch):
    assert m.underextracted(6, 113) and not m.underextracted(30, 113) and not m.underextracted(1, 10)
    slug, raw, row = _paper("YKQQZV93")
    count, _ = get_counter(allow_download=False)
    calls = []

    def fake(client, system, txt, valid, *a, **k):
        calls.append(client)
        return Extraction([], prompt_tokens=100, completion_tokens=10, seconds=1.0, chunks=1)

    monkeypatch.setattr(m, "extract_paper", fake)
    out = m.process_one(row, ROOT / "corpus", "first", "sys", count, load_taxon_table(), 12000, None, Options(), "retry")
    assert calls == ["first", "retry"] and out["retry"] == {"claims_first": 0, "claims_retry": 0}
    assert out["prompt_tokens"] == 200 and out["completion_tokens"] == 20          # both calls are counted
    calls.clear()
    m.process_one(row, ROOT / "corpus", "first", "sys", count, load_taxon_table(), 12000)
    assert calls == ["first"]                                                        # default: no retry
