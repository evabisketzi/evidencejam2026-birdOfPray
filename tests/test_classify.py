import pytest

from pipeline.preprocess.classify import classify_sentence as D, find_citations, has_own_cue


def test_parenthetical_group_with_e_g_is_one_citation_dropped_as_background():
    s = "In larger woodland, this would be more difficult (e.g., Drayton & Primack 1999; Nuzzo 1999)."
    d = D(s)
    assert not d.keep and d.reason == "cited_background"
    assert d.citations == ["(e.g., Drayton & Primack 1999; Nuzzo 1999)"]


@pytest.mark.parametrize("s", [
    "Peatlands store carbon (Vasander and Kettunen, 2006; Vitt, 2006).",
    "Exotics suppress natives (Smith 2003).",
    "Exotics suppress natives (Smith et al. 2003a, b).",
    "Exotics suppress natives (see Lee 2010).",
    "Fire is common (Smith & Jones 1999, 2001).",
    "Exotics suppress natives [12].",
    "Exotics suppress natives [12–15].",
    "Exotics suppress natives [3, 5].",
    "Smith (2003) found that fire reduced cover.",
    "Lee et al. (2010) found that fire reduced cover.",
    "Smith and Jones (2003) found that fire reduced cover.",
    "Lee et al. 2010 found that fire reduced cover.",
])
def test_other_work_without_own_cue_is_dropped(s):
    d = D(s)
    assert not d.keep and d.reason == "cited_background" and d.citations


@pytest.mark.parametrize("s,expected", [
    ("Our results agree with Smith et al. (2010) and others (Lee 2003; Jones & Ng 2005a, b).", "Our results agree with [ref] and others."),
    ("I transplanted ramets as described by Quinty and Rochefort (2003).", "I transplanted ramets as described by [ref]."),
    ("We found more weeds in plots (Smith 2003).", "We found more weeds in plots."),
    ("Water table was related to CH4 flux (Fig. 3; Smith 1999).", "Water table was related to CH4 flux (Fig. 3)."),
    ("In my study, cover fell [12].", "In my study, cover fell."),
])
def test_citation_with_own_cue_is_stripped_and_kept(s, expected):
    d = D(s)
    assert d.keep and d.reason == "own_cue_stripped" and d.text == expected


@pytest.mark.parametrize("s", [
    "Cover rose after burning.",
    "In 2005 Murphy planted 5 ramets (Table 2, 2001).",     # a year inside parentheses is not a citation
    "Samples were taken in plot A (n = 12, 2004).",
    "The density was 3 stems per m2 (Fig. 2).",
])
def test_no_citation_is_kept_untouched(s):
    d = D(s)
    assert d.keep and d.reason == "kept" and d.text == s and not d.citations


@pytest.mark.parametrize("s,expected", [
    ("I measured cover in each plot.", True),
    ("My study site was a woodlot.", True),
    ("We thank the reviewers.", True),
    ("Our plots were burned.", True),
    ("This study tested restoration.", True),
    ("The present study found no effect.", True),
    ("These results suggest planting works.", True),
    ("These data show a decline.", True),
    ("Here, cover declined.", True),
    ("In my plots, cover declined.", True),
    ("Cover increased (Fig. 3).", True),
    ("Peatlands store carbon.", False),
    ("Type I error was controlled.", False),
    ("Smith found that cover rose.", False),
])
def test_own_cue(s, expected):
    assert has_own_cue(s) is expected


def test_legend_species_plus_result_word_counts_as_own_cue():
    forms = ["Alliaria petiolata", "A. petiolata"]
    assert has_own_cue("A. petiolata decreased in density.", forms)
    assert not has_own_cue("A. petiolata is a biennial herb.", forms)
    assert not has_own_cue("A. petiolata decreased in density.", [])


def test_stripped_text_has_no_dangling_punctuation():
    d = D("We saw more cover ( Smith 2003 ), as expected.")
    assert d.keep and "( " not in d.text and " ," not in d.text and "()" not in d.text


def test_find_citations_reports_kinds():
    kinds = {c.kind for c in find_citations("Smith (2003) found it [4] (Lee 2010).")}
    assert kinds == {"inline", "numbered", "paren"}
