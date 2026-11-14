import pytest

from pipeline.preprocess.sentences import split_sentences as S


@pytest.mark.parametrize("text,expected", [
    # abbreviated genus is never a boundary
    ("Initial S. canadensis densities suppressed A. petiolata. Other species did not respond.",
     ["Initial S. canadensis densities suppressed A. petiolata.", "Other species did not respond."]),
    ("A. petiolata and S. canadensis co-occurred.", ["A. petiolata and S. canadensis co-occurred."]),
    # et al.
    ("This was shown by Lee et al. 2010. Then we measured it.",
     ["This was shown by Lee et al. 2010.", "Then we measured it."]),
    ("Lee et al. Found nothing.", ["Lee et al. Found nothing."]),
    # e.g. / i.e. / cf. / ca. / approx. / vs.
    ("Water was lower (e.g., Smith 1999; Lee et al. 2010). All else being equal, we saw more.",
     ["Water was lower (e.g., Smith 1999; Lee et al. 2010).", "All else being equal, we saw more."]),
    ("Cover rose, i.e. Rosa multiflora spread. Next.", ["Cover rose, i.e. Rosa multiflora spread.", "Next."]),
    ("Compare cf. Smith with ours. Done.", ["Compare cf. Smith with ours.", "Done."]),
    ("Approx. 20 plants died, ca. 5 m away. Next.", ["Approx. 20 plants died, ca. 5 m away.", "Next."]),
    ("Treated vs. Control plots differed. Yes.", ["Treated vs. Control plots differed.", "Yes."]),
    # Fig. / Figs. / Table / Eq. / No.
    ("Fig. 3 shows the effect. Table 2 lists means. See Figs. 3 and 4. Next sentence.",
     ["Fig. 3 shows the effect.", "Table 2 lists means.", "See Figs. 3 and 4.", "Next sentence."]),
    ("See Eq. 4 and Tab. 2; No. 5 plots failed.", ["See Eq. 4 and Tab. 2; No. 5 plots failed."]),
    ("See Eq. 4. Tab. 2 lists them.", ["See Eq. 4.", "Tab. 2 lists them."]),
    ("Did it work? Yes. No. 5 plots failed. Done!", ["Did it work?", "Yes.", "No. 5 plots failed.", "Done!"]),
    # spp. sp. subsp. var. ssp.
    ("Carex spp. and Juncus sp. dominated. Tree cover rose.", ["Carex spp. and Juncus sp. dominated.", "Tree cover rose."]),
    ("Acer rubrum var. rubrum and Pinus subsp. banksiana grew. Done.",
     ["Acer rubrum var. rubrum and Pinus subsp. banksiana grew.", "Done."]),
    # decimals and P-values
    ("Mean P was 0.05. The next was 0.07.", ["Mean P was 0.05.", "The next was 0.07."]),
    ("Cover was 12.5 percent. Density was 0.3 per m2.", ["Cover was 12.5 percent.", "Density was 0.3 per m2."]),
    ("It rained (P < 0.05.) Then it stopped.", ["It rained (P < 0.05.)", "Then it stopped."]),
    # initials in author names
    ("We thank S. D. Murphy and J. Smith. They helped.", ["We thank S. D. Murphy and J. Smith.", "They helped."]),
    ("Stephen D. Murphy designed it. It worked.", ["Stephen D. Murphy designed it.", "It worked."]),
    ("Bailey, D.D., A.Y. Fedorenko and R.J. Cook. 2005. An approach.",
     ["Bailey, D.D., A.Y. Fedorenko and R.J. Cook.", "2005.", "An approach."]),
    # one-letter treatment labels still end sentences
    ("Seedlings were counted in plot A. Rosettes were counted in plot B. Done.",
     ["Seedlings were counted in plot A.", "Rosettes were counted in plot B.", "Done."]),
    # units with periods
    ("Elevation was 300 m a.s.l. Temperature was 5 C. Done.", ["Elevation was 300 m a.s.l. Temperature was 5 C.", "Done."]),
    # captions
    ("Figure 1. Leafing phenologies for A. petiolata. Data are means.",
     ["Figure 1. Leafing phenologies for A. petiolata.", "Data are means."]),
    ("They were excluded from Table 1. Generally, it rose.", ["They were excluded from Table 1.", "Generally, it rose."]),
    # geography
    ("In the U.S. Forest Service lands, cover rose. In the U.S. The next.",
     ["In the U.S. Forest Service lands, cover rose.", "In the U.S.", "The next."]),
    # months
    ("Plots were burned on Dec. 5 in 1997. Then we waited.", ["Plots were burned on Dec. 5 in 1997.", "Then we waited."]),
    # parenthesis veto
    ("Effects were large (see Table 2. Results were similar elsewhere) and clear. Next.",
     ["Effects were large (see Table 2. Results were similar elsewhere) and clear.", "Next."]),
])
def test_split(text, expected):
    assert S(text) == expected


def test_no_sentence_lost_and_offsets_exact():
    from pipeline.preprocess.sentences import split_spans
    text = "First one. Second one (e.g., Smith 1999). Third S. canadensis one? Fourth!"
    spans = split_spans(text)
    assert [text[a:b] for a, b in spans] == S(text)
    assert all(text[a:b] == text[a:b].strip() for a, b in spans)
    covered = "".join(text[a:b] for a, b in spans).replace(" ", "")
    assert covered == text.replace(" ", "")
