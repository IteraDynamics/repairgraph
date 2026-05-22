from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)
from repairgraph.inference.repair_complexity import score_repair_complexity
from repairgraph.inference.material_risk import surface_material_risks
from repairgraph.inference.supplement_candidates import infer_supplement_candidates
from repairgraph.inference.motifs import find_corpus_motifs


def assert_evidence_object(evidence: dict):
    assert "source_type" in evidence
    assert "basis" in evidence
    assert "confidence" in evidence
    assert "requires_oem_verification" in evidence
    assert "interpretation" in evidence
    assert evidence["requires_oem_verification"] is True


# --- repair_complexity ---

def test_complexity_score_is_positive():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = score_repair_complexity(proc)
    assert result["score"] > 0


def test_complexity_tier_is_valid():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = score_repair_complexity(proc)
    assert result["tier"] in ("low", "moderate", "high", "critical")


def test_complexity_breakdown_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = score_repair_complexity(proc)
    breakdown = result["breakdown"]
    assert set(breakdown) == {
        "joining_methods",
        "replacement_dependencies",
        "sectioning_locations",
        "corrosion_requirements",
    }


def test_accord_more_complex_than_civic():
    # Accord has MIG brazing (weight 3) + more dependencies; Civic has only spot weld
    accord = score_repair_complexity(load_procedure("Honda", 2025, "Accord"))
    civic = score_repair_complexity(load_procedure("Honda", 2025, "Civic"))
    assert accord["score"] > civic["score"]


def test_mig_brazing_flagged_for_accord():
    result = score_repair_complexity(load_procedure("Honda", 2025, "Accord"))
    assert "mig_brazing_required" in result["risk_flags"]


def test_mig_brazing_not_flagged_for_civic():
    result = score_repair_complexity(load_procedure("Honda", 2025, "Civic"))
    assert "mig_brazing_required" not in result["risk_flags"]


def test_sectioning_flagged_for_crv():
    result = score_repair_complexity(load_procedure("Honda", 2025, "CR-V"))
    assert "sectioning_required" in result["risk_flags"]


def test_uhss_flag_requires_structure():
    proc = load_procedure("Honda", 2025, "Accord")
    without_structure = score_repair_complexity(proc)
    with_structure = score_repair_complexity(proc, load_vehicle_structure("Honda", 2025, "Accord"))
    assert "uhss_material_present" not in without_structure["risk_flags"]
    assert "uhss_material_present" in with_structure["risk_flags"]


# --- material_risk ---

def test_material_risk_returns_list():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)
    assert isinstance(result["material_risks"], list)
    assert len(result["material_risks"]) > 0


def test_material_risks_include_evidence_objects():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)

    for risk in result["material_risks"]:
        assert "evidence" in risk
        assert_evidence_object(risk["evidence"])


def test_uhss_component_flagged_for_accord():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)
    uhss = [r for r in result["material_risks"] if r["risk"] == "uhss_joining_constraint"]
    assert any(r["component"] == "rear_roof_rail_upper" for r in uhss)


def test_uhss_count_matches():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)
    uhss_in_list = sum(1 for r in result["material_risks"] if r["risk"] == "uhss_joining_constraint")
    assert result["uhss_component_count"] == uhss_in_list


def test_mig_brazing_gap_flagged_when_uhss_but_missing_from_procedure():
    # CR-V procedure has no mig_brazing; if evaluated against Accord structure (UHSS) → gap
    proc = load_procedure("Honda", 2025, "CR-V")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)
    uhss_risks = [r for r in result["material_risks"] if r.get("gap")]
    assert len(uhss_risks) > 0


def test_zinc_plated_components_listed():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = surface_material_risks(proc, structure)
    assert isinstance(result["zinc_plated_components"], list)
    assert "roof_panel" in result["zinc_plated_components"]


# --- supplement_candidates ---

def test_supplement_candidates_nonempty():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)
    assert result["total"] > 0


def test_supplement_candidates_include_evidence_objects():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)

    for candidate in result["supplement_candidates"]:
        assert "evidence" in candidate
        assert_evidence_object(candidate["evidence"])


def test_replacement_parts_are_supplement_candidates():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)
    parts = [c["item"] for c in result["by_category"]["parts"]]
    assert "rear_combination_adapter" in parts


def test_corrosion_requirements_become_candidates():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)
    mat_labor = [c["item"] for c in result["by_category"]["materials_and_labor"]]
    assert "sealer_application" in mat_labor


def test_sectioning_produces_labor_candidate():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)
    labor = [c["item"] for c in result["by_category"]["labor"]]
    assert "sectioning_labor" in labor


def test_mig_brazing_labor_for_accord_with_uhss_structure():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = infer_supplement_candidates(proc, structure)
    labor = [c["item"] for c in result["by_category"]["labor"]]
    assert "mig_brazing_labor" in labor


def test_by_category_covers_all_candidates():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = infer_supplement_candidates(proc)
    all_from_categories = (
        result["by_category"]["parts"]
        + result["by_category"]["materials_and_labor"]
        + result["by_category"]["labor"]
    )
    assert len(all_from_categories) == result["total"]


# --- motifs ---

def test_motifs_corpus_size():
    procedures = load_all_procedures()
    result = find_corpus_motifs(procedures)
    assert result["corpus_size"] == len(procedures)


def test_spot_weld_is_universal():
    result = find_corpus_motifs(load_all_procedures())
    assert "spot_weld" in result["universal_joining_methods"]


def test_sealer_is_universal_corrosion():
    result = find_corpus_motifs(load_all_procedures())
    assert "sealer_application_required" in result["universal_corrosion_requirements"]


def test_wheel_arch_separator_is_common():
    result = find_corpus_motifs(load_all_procedures())
    common_names = [m["component"] for m in result["common_components"]]
    assert "wheel_arch_separator" in common_names


def test_odyssey_has_model_specific_components():
    result = find_corpus_motifs(load_all_procedures())
    specific_models = {item["model"] for item in result["model_specific_components"]}
    assert "Odyssey" in specific_models


def test_common_component_frequency_is_valid():
    result = find_corpus_motifs(load_all_procedures())
    for item in result["common_components"]:
        assert 0 < item["frequency"] <= 1.0


def test_empty_corpus_handled():
    result = find_corpus_motifs([])
    assert result["corpus_size"] == 0
