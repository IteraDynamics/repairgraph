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
    Compare a procedure against the corpus motifs to surface components,
    joining methods, and corrosion requirements that the corpus considers
    common but this procedure does not mention.
    """
    motifs = find_corpus_motifs(corpus)

    if not corpus:
        return {
            "model": procedure.get("model"),
            "oem": procedure.get("oem"),
            "year": procedure.get("year"),
            "missing_components": [],
            "missing_joining_methods": [],
            "missing_corrosion_requirements": [],
            "total_gaps": 0,
        }

    present_components = _resolve_components(procedure)
    present_joining = set(get_joining_methods(procedure))
    present_corrosion = set(get_corrosion_requirements(procedure))

    missing_components = []
    for item in motifs["common_components"]:
        component = item["component"]
        if component not in present_components:
            missing_components.append({
                "component": component,
                "corpus_frequency": item["frequency"],
                "present_in": item["models"],
                "confidence": "high" if item["frequency"] >= 0.8 else "moderate",
            })

    missing_joining = [
        {
            "method": m,
            "note": "present in all corpus procedures",
            "confidence": "high",
        }
        for m in motifs["universal_joining_methods"]
        if m not in present_joining
    ]

    missing_corrosion = [
        {
            "requirement": r,
            "note": "present in all corpus procedures",
            "confidence": "high",
        }
        for r in motifs["universal_corrosion_requirements"]
        if r not in present_corrosion
    ]

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "missing_components": missing_components,
        "missing_joining_methods": missing_joining,
        "missing_corrosion_requirements": missing_corrosion,
        "total_gaps": len(missing_components) + len(missing_joining) + len(missing_corrosion),
    }
