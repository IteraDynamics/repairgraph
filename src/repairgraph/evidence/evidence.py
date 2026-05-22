ALLOWED_SOURCE_TYPES = {
    "normalized_procedure",
    "normalized_structure",
    "normalized_taxonomy",
    "graph_relationship",
    "corpus_pattern",
    "derived_inference",
    "manual_review",
}

ALLOWED_CONFIDENCE = {
    "high",
    "medium",
    "moderate",
    "low",
    "conditional",
}

ALLOWED_INTERPRETATIONS = {
    "source_observation",
    "normalized_fact",
    "graph_relationship",
    "advisory",
    "corpus_pattern",
}


def build_evidence(
    *,
    source_type: str,
    basis: list[str],
    confidence: str,
    requires_oem_verification: bool = True,
    interpretation: str = "advisory",
) -> dict:
    """
    Construct a standardized RepairGraph evidence object.

    Evidence objects exist to preserve provenance and trust semantics for
    advisory intelligence outputs.
    """

    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source_type}")

    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"Unsupported confidence: {confidence}")

    if interpretation not in ALLOWED_INTERPRETATIONS:
        raise ValueError(f"Unsupported interpretation: {interpretation}")

    if not basis:
        raise ValueError("basis must contain at least one evidence tag")

    return {
        "source_type": source_type,
        "basis": basis,
        "confidence": confidence,
        "requires_oem_verification": requires_oem_verification,
        "interpretation": interpretation,
    }
