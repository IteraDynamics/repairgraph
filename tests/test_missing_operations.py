from repairgraph.query.loader import load_all_procedures, load_procedure
from repairgraph.inference.missing_operations import detect_missing_operations


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def assert_evidence_object(evidence: dict):
    assert "source_type" in evidence
    assert "basis" in evidence
    assert "confidence" in evidence
    assert "requires_oem_verification" in evidence
    assert "interpretation" in evidence
    assert evidence["requires_oem_verification"] is True


def test_result_structure():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    assert "corpus_gap_components" in result
    assert "corpus_gap_joining_methods" in result
    assert "corpus_gap_corrosion_requirements" in result
    assert "total_gaps" in result
    assert "interpretation_note" in result


def test_total_gaps_is_sum_of_lists():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    assert result["total_gaps"] == (
        len(result["corpus_gap_components"])
        + len(result["corpus_gap_joining_methods"])
        + len(result["corpus_gap_corrosion_requirements"])
    )


def test_no_gaps_when_procedure_has_everything():
    # A procedure evaluated against an empty corpus has no corpus-pattern gaps.
    proc = load_procedure("Honda", 2025, "CR-V")
    result = detect_missing_operations(proc, [])
    assert result["total_gaps"] == 0


def test_corpus_gap_component_has_required_fields():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    for item in result["corpus_gap_components"]:
        assert "component" in item
        assert "corpus_frequency" in item
        assert "confidence" in item
        assert "advisory" in item
        assert "evidence" in item
        assert_evidence_object(item["evidence"])
        assert item["confidence"] in ("high", "moderate")


def test_confidence_high_for_high_frequency():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    high_conf = [m for m in result["corpus_gap_components"] if m["confidence"] == "high"]
    for item in high_conf:
        assert item["corpus_frequency"] >= 0.8


def test_pilot_flags_common_replacement_part_corpus_gaps():
    # Pilot has a different structure (rear_combination_stiffener, not rear_combination_adapter).
    # Corpus-gap outputs are advisory pattern signals, not definitive OEM omissions.
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    gaps = [m["component"] for m in result["corpus_gap_components"]]
    assert len(gaps) > 0


def test_corpus_gap_joining_methods_are_universal_only():
    # Only joining methods that appear in ALL corpus procedures should be flagged.
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    for item in result["corpus_gap_joining_methods"]:
        assert item["confidence"] == "high"
        assert "advisory" in item
        assert "evidence" in item
        assert_evidence_object(item["evidence"])


def test_corpus_gap_corrosion_requirements_include_evidence():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = detect_missing_operations(proc, _corpus_without("Pilot"))
    for item in result["corpus_gap_corrosion_requirements"]:
        assert "evidence" in item
        assert_evidence_object(item["evidence"])


def test_sealer_not_flagged_as_corpus_gap_when_procedure_has_it():
    proc = load_procedure("Honda", 2025, "CR-V")
    # CR-V has sealer_application_required; it should not appear as a corpus gap.
    result = detect_missing_operations(proc, _corpus_without("CR-V"))
    gap_corrosion = [m["requirement"] for m in result["corpus_gap_corrosion_requirements"]]
    assert "sealer_application_required" not in gap_corrosion


def test_model_label_in_result():
    proc = load_procedure("Honda", 2025, "Civic")
    result = detect_missing_operations(proc, _corpus_without("Civic"))
    assert result["model"] == "Civic"
    assert result["oem"] == "Honda"
    assert result["year"] == 2025
