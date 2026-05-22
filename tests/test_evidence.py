import pytest

from repairgraph.evidence import build_evidence


def test_build_valid_evidence_object():
    evidence = build_evidence(
        source_type="normalized_structure",
        basis=["vehicle_structure_material_map"],
        confidence="medium",
        interpretation="advisory",
    )

    assert evidence["source_type"] == "normalized_structure"
    assert evidence["confidence"] == "medium"
    assert evidence["requires_oem_verification"] is True
    assert evidence["interpretation"] == "advisory"
    assert evidence["basis"] == ["vehicle_structure_material_map"]


def test_requires_basis():
    with pytest.raises(ValueError):
        build_evidence(
            source_type="normalized_structure",
            basis=[],
            confidence="medium",
        )


@pytest.mark.parametrize(
    "source_type",
    [
        "normalized_procedure",
        "normalized_structure",
        "normalized_taxonomy",
        "graph_relationship",
        "corpus_pattern",
        "derived_inference",
        "manual_review",
    ],
)
def test_allowed_source_types(source_type):
    evidence = build_evidence(
        source_type=source_type,
        basis=["test_basis"],
        confidence="high",
    )
    assert evidence["source_type"] == source_type


@pytest.mark.parametrize(
    "confidence",
    ["high", "medium", "low", "conditional"],
)
def test_allowed_confidence_values(confidence):
    evidence = build_evidence(
        source_type="derived_inference",
        basis=["test_basis"],
        confidence=confidence,
    )
    assert evidence["confidence"] == confidence


def test_invalid_source_type_raises():
    with pytest.raises(ValueError):
        build_evidence(
            source_type="magic_ai_truth",
            basis=["test_basis"],
            confidence="high",
        )


def test_invalid_confidence_raises():
    with pytest.raises(ValueError):
        build_evidence(
            source_type="derived_inference",
            basis=["test_basis"],
            confidence="certain",
        )


def test_invalid_interpretation_raises():
    with pytest.raises(ValueError):
        build_evidence(
            source_type="derived_inference",
            basis=["test_basis"],
            confidence="medium",
            interpretation="objective_truth",
        )
