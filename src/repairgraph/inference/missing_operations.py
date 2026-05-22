from repairgraph.evidence import build_evidence
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
            "interpretation_note": (
                "Corpus-gap outputs identify patterns across the normalized corpus and should not "
                "be interpreted as definitive OEM omissions."
            ),
        }

    present_components = _resolve_components(procedure)
    present_joining = set(get_joining_methods(procedure))
    present_corrosion = set(get_corrosion_requirements(procedure))

    corpus_gap_components = []
    for item in motifs["common_components"]:
        component = item["component"]
        if component not in present_components:
            confidence = "high" if item["frequency"] >= 0.8 else "moderate"
            evidence = build_evidence(
                source_type="corpus_pattern",
                basis=["corpus_common_component"],
                confidence=confidence,
                interpretation="corpus_pattern",
            )
            corpus_gap_components.append({
                "component": component,
                "corpus_frequency": item["frequency"],
                "present_in": item["models"],
                "confidence": evidence["confidence"],
                "advisory": (
                    "Common in comparable procedures but not present in this normalized object. "
                    "Verify applicability against the OEM source procedure."
                ),
                "evidence": evidence,
            })

    corpus_gap_joining = []
    for method in motifs["universal_joining_methods"]:
        if method not in present_joining:
            evidence = build_evidence(
                source_type="corpus_pattern",
                basis=["corpus_universal_joining_method"],
                confidence="high",
                interpretation="corpus_pattern",
            )
            corpus_gap_joining.append({
                "method": method,
                "note": "present in all corpus procedures",
                "confidence": evidence["confidence"],
                "advisory": "Verify whether this joining method is applicable to the current procedure.",
                "evidence": evidence,
            })

    corpus_gap_corrosion = []
    for requirement in motifs["universal_corrosion_requirements"]:
        if requirement not in present_corrosion:
            evidence = build_evidence(
                source_type="corpus_pattern",
                basis=["corpus_universal_corrosion_requirement"],
                confidence="high",
                interpretation="corpus_pattern",
            )
            corpus_gap_corrosion.append({
                "requirement": requirement,
                "note": "present in all corpus procedures",
                "confidence": evidence["confidence"],
                "advisory": "Verify whether this corrosion requirement applies to the current procedure.",
                "evidence": evidence,
            })

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
