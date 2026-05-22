from repairgraph.inference.motifs import find_corpus_motifs
from repairgraph.taxonomy.aliases import resolve_alias
from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_inspection_dependencies,
    get_corrosion_requirements,
)


def _resolve_components(procedure: dict) -> set[str]:
    return {
        resolve_alias(c)
        for c in (
            get_replacement_dependencies(procedure)
            + get_inspection_dependencies(procedure)
        )
    }


def detect_missing_operations(procedure: dict, corpus: list[dict]) -> dict:
    """
    Compare a procedure against corpus motifs to surface potentially relevant
    components, joining methods, or corrosion requirements that appear commonly
    across similar procedures but are absent from this normalized procedure object.

    These outputs are advisory corpus-pattern signals, not authoritative OEM omissions.
    """
    motifs = find_corpus_motifs(corpus)

    if not corpus:
        return {
            "model": procedure.get("model"),
            "oem": procedure.get("oem"),
            "year": procedure.get("year"),
            "corpus_gap_components": [],
            "corpus_gap_joining_methods": [],
            "corpus_gap_corrosion_requirements": [],
            "total_gaps": 0,
        }

    present_components = _resolve_components(procedure)
    present_joining = set(get_joining_methods(procedure))
    present_corrosion = set(get_corrosion_requirements(procedure))

    corpus_gap_components = []
    for item in motifs["common_components"]:
        component = item["component"]
        if component not in present_components:
            corpus_gap_components.append({
                "component": component,
                "corpus_frequency": item["frequency"],
                "present_in": item["models"],
                "confidence": "high" if item["frequency"] >= 0.8 else "moderate",
                "advisory": (
                    "Common in comparable procedures but not present in this normalized object. "
                    "Verify applicability against the OEM source procedure."
                ),
            })

    corpus_gap_joining = [
        {
            "method": m,
            "note": "present in all corpus procedures",
            "confidence": "high",
            "advisory": "Verify whether this joining method is applicable to the current procedure.",
        }
        for m in motifs["universal_joining_methods"]
        if m not in present_joining
    ]

    corpus_gap_corrosion = [
        {
            "requirement": r,
            "note": "present in all corpus procedures",
            "confidence": "high",
            "advisory": "Verify whether this corrosion requirement applies to the current procedure.",
        }
        for r in motifs["universal_corrosion_requirements"]
        if r not in present_corrosion
    ]

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "corpus_gap_components": corpus_gap_components,
        "corpus_gap_joining_methods": corpus_gap_joining,
        "corpus_gap_corrosion_requirements": corpus_gap_corrosion,
        "total_gaps": len(corpus_gap_components) + len(corpus_gap_joining) + len(corpus_gap_corrosion),
        "interpretation_note": (
            "Corpus-gap outputs identify patterns across the normalized corpus and should not "
            "be interpreted as definitive OEM omissions."
        ),
    }
