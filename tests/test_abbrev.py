from pipeline.expand import expand_claims
from pipeline.parse import parse_text
from pipeline.preprocess.abbrev import expand_abbreviations, find_abbreviations


def test_schwartz_hearst_definitions():
    text = ("Soil volumetric moisture content (VMC, %) was logged. We measured net ecosystem production (NEP) and "
            "Acid mine drainage (AMD) was treated. Polycyclic aromatic hydrocarbons (PAHs) and greenhouse gases (GHGs) fell. "
            "Sørensen's coefficient of similarity (SCS) rose. Cover was high (Fig. 2) at the site (SD) (2004) (n = 5) (pH).")
    a = find_abbreviations(text)
    assert a["VMC"] == "volumetric moisture content"
    assert a["NEP"] == "net ecosystem production"
    assert a["AMD"] == "acid mine drainage"                  # sentence-initial capital dropped
    assert a["PAH"] == "polycyclic aromatic hydrocarbon"
    assert a["GHG"] == "greenhouse gas"
    assert a["SCS"].startswith("Sørensen's")                 # a name keeps its capital
    assert not {"Fig", "SD", "pH"} & set(a)


def test_expansion_keeps_the_abbreviation_and_never_nests_or_repeats():
    a = {"VMC": "volumetric moisture content", "NEP": "net ecosystem production", "CT": "consolidated tailings"}
    assert expand_abbreviations("Soil VMC", a) == "Soil volumetric moisture content (VMC)"
    assert expand_abbreviations("Increased NEP", a) == "Increased net ecosystem production (NEP)"
    assert expand_abbreviations("net ecosystem production (NEP)", a) == "net ecosystem production (NEP)"
    assert expand_abbreviations("Site (Suncor CT+NW)", a) == "Site (Suncor CT+NW)"
    assert expand_abbreviations("NEPTUNE index", a) == "NEPTUNE index"            # whole tokens only
    assert expand_abbreviations("VMC and VMC", a) == "volumetric moisture content (VMC) and VMC"


def test_node_names_and_attributes_are_expanded_from_the_sidecar():
    side = {"sentences": [{"n": 1, "section": "res", "clean": "Higher VMC increased NEP.", "start_char": 0, "end_char": 25}],
            "species": [], "abbreviations": {"VMC": "volumetric moisture content", "NEP": "net ecosystem production"}}
    claims, _ = parse_text("F|1|soil/VMC/+/var|c|NEP/+/var|D|exp")
    nodes = expand_claims("X", claims, side).nodes
    names = sorted(n["name"] for n in nodes.values())
    assert names == ["Increased net ecosystem production (NEP)", "Increased volumetric moisture content (VMC) of soil"]
    attrs = [n.get("measured_attribute") for n in nodes.values() if n.get("measured_attribute")]
    assert attrs == ["volumetric moisture content (VMC)"]


def test_cap_keeps_mixed_case_terms():
    from pipeline.expand import _cap
    assert _cap("pH") == "pH"
    assert _cap("pH of soil") == "pH of soil"
    assert _cap("eDNA detection") == "eDNA detection"
    assert _cap("soil moisture") == "Soil moisture"
    assert _cap("") == ""
