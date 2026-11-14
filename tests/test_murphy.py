"""End-to-end check against the hand-annotated Murphy 2005 gold (25 findings).

Murphy 2005 is in the corpus as YKQQZV93, so the corpus markdown is used.  The gold `sentence` fields are
rewritten summaries (fit: lossy), so findings are matched to kept sentences by word overlap.
"""
import csv
import re
from pathlib import Path

import pytest
import yaml

from pipeline.preprocess.assemble import Options, process_paper
from pipeline.preprocess.classify import find_citations
from pipeline.preprocess.clean import clean
from pipeline.preprocess.legend import load_taxon_table
from pipeline.preprocess.sections import detect_sections
from pipeline.preprocess.tokens import get_counter

ROOT = Path(__file__).resolve().parent.parent
SLUG = "YKQQZV93"
THRESHOLD = 0.5
STOP = {"that", "with", "from", "were", "this", "than", "have", "which", "their", "there", "these", "those", "been",
        "when", "also", "both", "each", "more", "most", "such", "into", "over", "only", "other", "then", "they"}


@pytest.fixture(scope="module")
def raw():
    return (ROOT / "corpus" / f"{SLUG}.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def result(raw):
    meta = next(r for r in csv.DictReader(open(ROOT / "corpus" / "index.csv", encoding="utf-8")) if r["slug"] == SLUG)
    count, _ = get_counter(allow_download=False)
    return process_paper(SLUG, raw, meta, count, Options(), load_taxon_table())


@pytest.fixture(scope="module")
def gold():
    d = yaml.safe_load(open(ROOT / "example" / "Murphy2005.yaml", encoding="utf-8"))
    return [(g["finding_id"], g["sentence"]) for g in d["graphs"]]


def _species_words(side):
    words = set()
    for sp in side["species"]:
        words |= {w.lower() for w in re.findall(r"[A-Za-z]+", sp["name"])}
    return words


def _tokens(text, skip):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3 and w not in STOP and w not in skip}


def match_table(result, gold):
    sents = result.sidecar["sentences"]
    skip = _species_words(result.sidecar)
    rows = []
    for fid, g in gold:
        ft = _tokens(g, skip)
        best = (0.0, None, None)
        for i, s in enumerate(sents):
            windows = [([s], s["clean"])]
            if i + 1 < len(sents) and sents[i + 1]["section"] == s["section"]:
                windows.append(([s, sents[i + 1]], s["clean"] + " " + sents[i + 1]["clean"]))
            for ss, txt in windows:
                score = len(ft & _tokens(txt, skip)) / max(1, len(ft))
                if score > best[0] + 1e-9:
                    best = (score, [x["n"] for x in ss], ss[0]["section"])
        rows.append((fid, best[1], best[2], best[0]))
    return rows


def test_match_table_every_gold_finding_has_a_kept_sentence(result, gold, capsys):
    rows = match_table(result, gold)
    lines = [f"{'finding':<8}{'sentence no.':<14}{'section':<9}{'overlap':>8}"]
    for fid, nums, sec, sc in rows:
        lines.append(f"{fid:<8}{'+'.join(map(str, nums)) if nums else '-':<14}{sec or '-':<9}{sc:>8.2f}")
    with capsys.disabled():
        print("\n" + "\n".join(lines))
    missing = [(fid, round(sc, 2)) for fid, _, _, sc in rows if sc < THRESHOLD]
    assert not missing, f"gold findings without a kept numbered sentence (overlap < {THRESHOLD}): {missing}"
    assert len(rows) == 25


def test_gold_sections_are_abstract_results_discussion(result, gold):
    secs = {r[2] for r in match_table(result, gold)}
    assert secs <= {"abs", "res", "dis"}


def test_no_introduction_or_methods_sentence_is_numbered(result, raw):
    assert {s["section"] for s in result.sidecar["sentences"]} <= {"abs", "res", "dis", "con", "lim", "cap"}
    cleaned = clean(raw).cleaned
    sr = detect_sections(cleaned)
    banned = [cleaned.raw_span(p.start, p.end) for p in sr.paras if p.section in ("int", "met") and p.kind == "body"]
    assert banned, "Murphy has Introduction and Methods sections"
    for s in result.sidecar["sentences"]:
        assert not any(a <= s["start_char"] < b for a, b in banned), s["clean"][:80]


def test_known_trap_sentences_are_kept(result):
    by = {s["n"]: s for s in result.sidecar["sentences"]}
    f26 = [s for s in by.values() if "resulted in more successful competition" in s["clean"]]
    f32 = [s for s in by.values() if "cost and labor effective" in s["clean"]]
    assert f26 and f26[0]["section"] == "dis"
    assert f32 and f32[0]["section"] == "dis"
    # the cited neighbour of f26 is dropped, not merged into it
    assert "Drayton" not in f26[0]["clean"]
    # f32 was split across a table and two figures by the converter and is whole again
    assert f32[0]["clean"].endswith("hundred meters at most.")


def test_cited_background_without_own_cue_is_dropped(result):
    num = " ".join(s["clean"] for s in result.sidecar["sentences"])
    assert "Drayton & Primack" not in num
    dropped = [d for d in result.sidecar["dropped"] if d["reason"] == "cited_background"]
    assert any("this would be more difficult" in d["clean"] for d in dropped)
    assert any("Anand & Desrochers" in c for d in dropped for c in d["citations"])
    for s in result.sidecar["sentences"]:
        assert not find_citations(s["compressed"]), s["compressed"]


def test_abstract_methods_plus_first_result_finding_f1(result, gold):
    f1 = dict(gold)["f1"]
    row = next(r for r in match_table(result, gold) if r[0] == "f1")
    assert row[2] == "abs" and row[3] >= THRESHOLD, (f1, row)


def test_offsets_point_back_into_the_raw_text(result, raw):
    norm = lambda t: re.sub(r"[^A-Za-z0-9]", "", re.sub(r"<[^>]+>", "", t))
    for s in result.sidecar["sentences"]:
        assert 0 <= s["start_char"] < s["end_char"] <= len(raw)
        assert s["raw"] == raw[s["start_char"]:s["end_char"]]
        c, r = norm(s["clean"]), norm(s["raw"])   # markup (italics, LaTeX) differs mid-sentence; ends must agree
        assert c[:14] == r[:14] and c[-8:] == r[-8:], (s["clean"], s["raw"])


def test_species_legend_has_ncbi_ids_matching_the_gold(result):
    sp = {x["name"]: x for x in result.sidecar["species"]}
    assert sp["Sanguinaria canadensis"]["ncbitaxon"] == "NCBITaxon:3472"
    assert sp["Alliaria petiolata"]["ncbitaxon"] == "NCBITaxon:126270"
    assert "S. canadensis" in sp["Sanguinaria canadensis"]["variants"]
    assert result.txt.splitlines()[1].startswith("SPECIES: T1=")


def test_output_format_and_determinism(result, raw):
    lines = result.txt.splitlines()
    assert lines[0].startswith("TITLE: Concurrent Management")
    assert lines[2].startswith("CONTEXT: ") and len(lines[2]) > 40
    assert lines[3] == "TEXT:"
    nums = [int(re.match(r"\[(\d+)\] \((abs|res|dis|con|lim|cap)\) ", l).group(1)) for l in lines[4:]]
    assert nums == list(range(1, len(nums) + 1))
    meta = {"title": result.sidecar["title"], "doi": result.sidecar["doi"]}
    count, _ = get_counter(allow_download=False)
    again = process_paper(SLUG, raw, {**meta, **{k: result.sidecar[k] for k in ("authors", "year", "journal", "word_count")}},
                          count, Options(), load_taxon_table())
    assert again.txt == result.txt
