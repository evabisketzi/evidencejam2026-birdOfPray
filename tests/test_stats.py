import pytest

from pipeline.preprocess.stats import compress_stats as C, detect_alpha, p_significance


@pytest.mark.parametrize("s,expected", [
    ("Cover differed (F2,36 = 4.51, P = 0.018) among plots.", "Cover differed [sig] among plots."),
    ("Cover differed (F(2, 36) = 4.51, P = 0.018).", "Cover differed [sig]."),
    ("Cover differed (F 2,36 = 4.51, p < 0.001).", "Cover differed [sig]."),
    ("No effect (t = 1.2, df = 18, P = 0.24).", "No effect [ns]."),
    ("No effect (t18 = 1.2, P = 0.24).", "No effect [ns]."),
    ("Strong (P < 0.001).", "Strong [sig]."),
    ("Weak (P > 0.05).", "Weak [ns]."),
    ("Weak (p=.08).", "Weak [ns]."),
    ("Declined (χ2 = 5.2, df = 1, P > 0.05).", "Declined [ns]."),
    ("Declined (chi2 = 9.2, df = 1, P = 0.002).", "Declined [sig]."),
    ("Ranked (H = 3.1, P = 0.2).", "Ranked [ns]."),
    ("Ranked (U = 31, P = 0.01).", "Ranked [sig]."),
    ("Ranked (W = 31, P = 0.01).", "Ranked [sig]."),
    ("Correlated (r = 0.45, P = 0.03).", "Correlated [sig]."),
    ("Correlated (R2 = 0.45, P = 0.03).", "Correlated [sig]."),
    ("Correlated (r2 = 0.45, df = 20, P < 0.01).", "Correlated [sig]."),
    ("Plain (P ≤ 0.05).", "Plain [sig]."),
    ("Plain (P ≥ 0.2).", "Plain [ns]."),
    ("Plain (ns).", "Plain [ns]."),
    ("Kept the figure ref (Fig. 3; P < 0.05).", "Kept the figure ref (Fig. 3; [sig])."),
    ("Two groups (P < 0.001) and (P = 0.4).", "Two groups [sig] and [ns]."),
])
def test_compress(s, expected):
    assert C(s)[0] == expected


@pytest.mark.parametrize("s", [
    "Odd (n = 5, mean = 3, P < 0.05) stays.",            # unknown content -> unchanged
    "Test only (F = 3.0) stays.",                          # no p-value -> significance unknown
    "Vague (P < 0.10) stays at alpha 0.05.",              # cannot be decided
    "Mixed (P < 0.05 and P > 0.1) stays.",
    "Effect size (F2,36 = 4.51, P = 0.018, eta = 0.2) stays.",
    "No stats here (Fig. 3).",
])
def test_unparsed_is_left_unchanged(s):
    assert C(s)[0] == s


def test_alpha_is_taken_from_the_text():
    text = "Significance was assessed at α = 0.10."
    assert detect_alpha(text) == 0.10
    assert detect_alpha("alpha = 0.1 was used") == 0.1
    assert detect_alpha("nothing here") == 0.05
    s = "Cover differed (F = 3.0, P = 0.08)."
    assert C(s, 0.05)[0] == "Cover differed [ns]."
    assert C(s, 0.10)[0] == "Cover differed [sig]."


def test_p_significance_edges():
    assert p_significance("=", 0.05, 0.05) is False       # significant means P < alpha
    assert p_significance("<", 0.05, 0.05) is True
    assert p_significance("<", 0.10, 0.05) is None


def test_dispersion_terms_are_dropped_means_kept():
    assert C("Height was 12.3 ± 1.2 SE m.")[0] == "Height was 12.3 m."
    assert C("Height was 12.3 (± 1.2 SD).")[0] == "Height was 12.3."
    assert C("Height was 12.3 ± 1.2 and 9.1 ± 0.8 cm.")[0] == "Height was 12.3 and 9.1 cm."
    assert C("Heights (mean ± SE) were 12.3.")[0] == "Heights were 12.3."


def test_original_values_are_extractable_from_the_record():
    _, recs = C("Cover differed (F2,36 = 4.51, P = 0.018).")
    r = recs[0]
    assert r["original"] == "(F2,36 = 4.51, P = 0.018)"
    assert r["p_value"] == 0.018 and r["p_op"] == "=" and r["significance"] == "significant" and r["tests"] == ["F"]


def test_stats_compression_saves_tokens():
    from pipeline.preprocess.tokens import get_counter
    count, _ = get_counter(allow_download=False)
    s = "Cover differed (F2,36 = 4.51, P = 0.018) among plots."
    assert count(C(s)[0]) < count(s)
