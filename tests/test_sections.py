from pipeline.preprocess.clean import clean
from pipeline.preprocess.sections import detect_sections, heading_code, heading_code_fuzzy, looks_like_names


def tagged(md):
    c = clean(md).cleaned
    sr = detect_sections(c)
    return [(p.tag, p.text[:40]) for p in sr.paras if p.keep], sr


def test_exact_and_numbered_and_spaced_headings():
    assert heading_code("## 2. Materials and Methods") == "met"
    assert heading_code("#### a b s t r a c t") == "abs"
    assert heading_code("# **RESULTS**") == "res"
    assert heading_code("Literature Cited") == "ref"
    assert heading_code("# Implications for Practice") == "con"
    assert heading_code("# Study Site") == "met"
    assert heading_code("# Some Random Subheading") is None


def test_fuzzy_headings_only_move_forward():
    assert heading_code_fuzzy("#### Analysis and Results", "met") == "res"
    assert heading_code_fuzzy("# Study Site and Experimental Design", "int") == "met"
    assert heading_code_fuzzy("#### Implications for Ecological Restoration", "dis") == "con"
    assert heading_code_fuzzy("### Methods of analysis", "res") is None      # would go backwards


def test_parenthetical_heading_and_reference_subheadings():
    # ECK26ZFG
    assert heading_code("# Results (interim results for the ponderosa pine site only)") == "res"
    # ANWITZVF, 3YNFB29I, R7HU9C7W: subsections ABOUT reference sites are not the reference list
    assert heading_code_fuzzy("### SHIFTING REFERENCE CONDITION", "res") is None
    assert heading_code_fuzzy("### Comparisons with reference streams", "res") is None
    assert heading_code_fuzzy("## 2.1.2 Reference sites", "met") is None
    assert heading_code_fuzzy("## REFERENCES CITED", "dis") == "ref"
    assert heading_code_fuzzy("# Literature Cited and References", "dis") == "ref"


def test_results_subsections_after_reference_subheading_are_kept():
    md = ("# Title\n\n## Abstract\n\nWe tested X. We found Y.\n\n## Methods\n\nWe sampled lakes.\n\n### Results\n\n"
          "### SHIFTING REFERENCE CONDITION\n\nReference richness rose over time.\n\n### ASSESSMENT OF RECOVERY\n\n"
          "Richness recovered in two lakes.\n\n### Discussion\n\nRecovery is slow.\n\n### References\n\n"
          "Smith, J. 2000. A paper. Journal 1:1.\n")
    kept, sr = tagged(md)
    assert [t for t, _ in kept] == ["abs", "res", "res", "dis"]


def test_topic_headings_after_data_analysis_become_results():
    # 6DBK8P4E / 4RFTRJCP: Methods ... Data analysis, then result topics, then Discussion, no Results heading
    md = ("# Title\n\n## Abstract\n\nWe tested X. We found Y.\n\n## Methods\n\n## Study site\n\nA fen.\n\n"
          "### Carbon gas exchange\n\nChambers were used.\n\n# Data analysis\n\nWe used ANOVA.\n\n"
          "# Climate and hydrology\n\nThe summer was dry.\n\n### Carbon gas exchanges\n\nUptake fell.\n\n"
          "## Discussion\n\nDry years matter.\n")
    kept, sr = tagged(md)
    assert [(t, x.strip()) for t, x in kept] == [("abs", "We tested X. We found Y."), ("res", "The summer was dry."),
                                         ("res", "Uptake fell."), ("dis", "Dry years matter.")]
    assert "results_after_analysis" in sr.fallbacks
    # without an analysis subsection nothing is forced (frameworks / reports keep their structure)
    kept, sr = tagged(md.replace("# Data analysis", "# Sampling"))
    assert [t for t, _ in kept] == ["abs", "dis"]


def test_intro_and_methods_are_cut_results_discussion_kept():
    md = ("# Title\n\n## Abstract\n\n" + "We tested X. " * 3 + "\n\n## Introduction\n\nIntro text here. More intro.\n\n"
          "## Methods\n\nWe planted plots.\n\n## Results\n\nCover rose.\n\n## Discussion\n\nIt worked.\n\n"
          "## References\n\nSmith, J. 2000. A paper. Journal 1:1.\n")
    kept, sr = tagged(md)
    assert [t for t, _ in kept] == ["abs", "res", "dis"]
    assert sr.sections_detected == ["abs", "int", "met", "res", "dis", "ref"]
    assert sr.intro_aims.startswith("Intro text")
    assert [p.text for p in sr.methods] == ["We planted plots."]


def test_keywords_line_closes_an_unheaded_abstract():
    abstract = "We tested whether restoration changed cover in boreal peatlands. Cover rose after rewetting in all sites. " * 3
    md = f"# Title\n\n{abstract}\n\nKeywords: peat, cover\n\nThe introduction starts here without a heading. " \
         "It goes on for a while and cites others. " * 3 + "\n\n## Methods\n\nSites were sampled.\n\n## Results\n\nCover rose.\n"
    kept, sr = tagged(md)
    tags = [t for t, _ in kept]
    assert tags[0] == "abs" and "res" in tags
    assert not any("introduction starts" in x for _, x in kept)
    assert "front_as_abstract" in sr.fallbacks


def test_inline_abstract_label_and_french_resume_and_names():
    prose = ("Diversity and productivity of stream food webs are related to habitat complexity in many streams. "
             "We placed boulder clusters in a small stream and measured organic matter and invertebrates over two years. ")
    md = ("# Title\n\nJ. Negishi and J. Richardson Abstract: " + prose * 2 + "\n\n"
          "Résumé : Il existe une relation entre la diversité et la productivité des réseaux alimentaires en eau courante. " * 3
          + "\n\n## Introduction\n\nIntro.\n\n## Results\n\nCover rose.\n")
    kept, _ = tagged(md)
    assert kept[0][0] == "abs" and kept[0][1].startswith("Diversity and productivity")
    assert not any(x.startswith("Résumé") for _, x in kept)
    assert looks_like_names("Étienne Paradis1, Line Rochefort1")
    assert not looks_like_names("Cover rose after burning in the wet plots.")


def test_review_without_results_headings_keeps_its_body():
    md = ("# Review\n\n## Abstract\n\n" + "A review of lake recovery. " * 10 + "\n\n## 1 Introduction\n\nBackground text. More.\n\n"
          "#### 2 Changes in Lake Chemistry\n\nChemistry improved after controls.\n\n#### 3 Biological Recovery\n\nFish returned.\n\n"
          "## 5 Conclusions\n\nRecovery is slow.\n\n### References\n\nSmith, J. 2000. A paper. Journal 1:1.\n")
    kept, sr = tagged(md)
    texts = " ".join(x for _, x in kept)
    assert "Chemistry improved" in texts and "Fish returned" in texts and "Background text" not in texts
    assert "no_results_heading" in sr.fallbacks


def test_table_rows_dropped_caption_and_footnote_handled():
    md = ("## Results\n\nCover rose (Table 1).\n\nTable 1. Cover by treatment.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
          "Tests were based on data from 40 plots.\n\nAnother real sentence.\n")
    kept, _ = tagged(md)
    texts = [x for _, x in kept]
    assert any(x.startswith("Table 1. Cover") for x in texts) and not any("|" in x for x in texts)
    assert not any(x.startswith("Tests were based") for x in texts)
    assert any(x.startswith("Another real") for x in texts)


def test_no_headings_at_all_is_treated_as_results_minus_references():
    topics = ["soil", "fire", "peat", "fish", "birds", "moss", "ants", "seed"]
    refs = "\n\n".join(f"Writer{n}, A. B. 20{10 + i}. Title of paper on {n} cover. Journal {n}:1-10." for i, n in enumerate(topics))
    md = "Cover rose after burning. " * 20 + "\n\n" + refs + "\n"
    kept, sr = tagged(md)
    assert {t for t, _ in kept} == {"res"}
    assert "no_headings" in sr.fallbacks and "refs_heuristic" in sr.fallbacks
    assert not any("Title of paper" in x for _, x in kept)


def test_split_paragraphs_and_floats_are_rejoined_without_losing_offsets():
    raw = ("## Discussion\n\nTransplanting would be cost and labor\n\nTable 3. A caption.\n\n"
           "Tests were based on data.\n\neffective on a local scale. Next one.\n")
    c = clean(raw).cleaned
    assert "cost and labor effective on a local scale." in c.s
    a = c.s.index("effective")
    r0, r1 = c.raw_span(a, a + 9)
    assert raw[r0:r1] == "effective"


def test_hyphen_rejoin_keeps_real_hyphens():
    raw = ("## Results\n\nThe restora- tion of long-term plots was long-\nterm work. Plots were pre- and post-treatment. "
           "Restoration helps. A long- term view helps.\n")
    s = clean(raw).cleaned.s
    assert "restoration of long-term plots" in s
    assert "was long-term work" in s
    assert "pre- and post-treatment" in s
    assert "A long-term view" in s


def test_artifacts_removed():
    raw = ("## Results\n\n![](_page_0_Picture_5.jpeg)\n\n<!-- image -->\n\nCover <sup>2</sup> rose at <i>Carex</i> sites "
           "[link](#page-8-0) (see https://example.org/x and 10.1111/abc.123). Contact me@x.org.\n\n12\n\nRunning Header\n\n"
           "Running Header\n\nRunning Header\n\n<img alt=\"x\" src=\"data:image/png;base64," + "A" * 300 + "\">\n")
    s = clean(raw).cleaned.s
    for bad in ("_page_", "image", "<sup>", "<i>", "](", "example.org", "10.1111", "me@x.org", "Running Header", "base64"):
        assert bad not in s, bad
    assert "Cover 2 rose at Carex sites link" in s


def test_reference_string_inside_the_abstract_block_is_dropped():
    md = ("## Abstract\n\nBailey, D.D., A.Y. Fedorenko and R.J. Cook. 2005. An integrated approach to rebuilding chum. "
          "Can. Tech. Rep. Fish. Aquat. Sci. 2599.\n\nChum returns increased after flow control. Hatchery output was stable "
          "and escapement rose in every year of the study period.\n\n## Results\n\nCover rose.\n")
    kept, _ = tagged(md)
    texts = " ".join(x for _, x in kept)
    assert "Bailey" not in texts and "Chum returns increased" in texts
