from repairgraph.query.loader import load_all_procedures, load_procedure
from repairgraph.inference.missing_operations import detect_missing_operations


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def test_result_structure():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    assert "missing_components" in result
    assert "missing_joining_methods" in result
    assert "missing_corrosion_requirements" in result
    assert "total_gaps" in result


def test_total_gaps_is_sum_of_lists():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    assert result["total_gaps"] == (
        len(result["missing_components"])
        + len(result["missing_joining_methods"])
        + len(result["missing_corrosion_requirements"])
    )


def test_no_gaps_when_procedure_has_everything():
    # A procedure evaluated against an empty corpus has no gaps
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, [])
    assert result["total_gaps"] == 0


def test_missing_component_has_required_fields():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    for item in result["missing_components"]:
        assert "component" in item
        assert "corpus_frequency" in item
        assert "confidence" in item
        assert item["confidence"] in ("high", "moderate")


def test_confidence_high_for_high_frequency():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    high_conf = [m for m in result["missing_components"] if m["confidence"] == "high"]
    for item in high_conf:
        assert item["corpus_frequency"] >= 0.8


def test_pilot_missing_common_replacement_parts():
    # Pilot has a different structure (rear_combination_stiffener, not rear_combination_adapter)
    # wheel_arch_separator and rear_pillar_separator are common across other models
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    missing = [m["component"] for m in result["missing_components"]]
    # At minimum one common component should be flagged as missing for Pilot
    assert len(missing) > 0


def test_missing_joining_methods_are_universal_only():
    # Only joining methods that appear in ALL corpus procedures should be flagged
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    for item in result["missing_joining_methods"]:
        assert item["confidence"] == "high"


def test_sealer_not_missing_when_procedure_has_it():
    proc = load_procedure("Honda", 2025, "CR-V")
    # CR-V has sealer_application_required; it should not appear as missing
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    missing_corrosion = [m["requirement"] for m in result["missing_corrosion_requirements"]]
    assert "sealer_application_required" not in missing_corrosion


def test_model_label_in_result():
    proc = load_procedure("Honda", 2025, "Civic")
    result = detect_missing_operations(proc, _corpus_without("Civic"))
    assert result["model"] == "Civic"
    assert result["oem"] == "Honda"
    assert result["year"] == 2025
