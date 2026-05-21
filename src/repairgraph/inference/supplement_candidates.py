from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_corrosion_requirements,
    get_sectioning_locations,
    get_uhss_components,
)


_CORROSION_ITEMS = {
    "sealer_application_required": {
        "item": "sealer_application",
        "category": "materials_and_labor",
        "confidence": "high",
    },
    "adhesive_application_required": {
        "item": "adhesive_application",
        "category": "materials_and_labor",
        "confidence": "high",
    },
    "urethane_foam_replacement_required": {
        "item": "urethane_foam_replacement",
        "category": "materials_and_labor",
        "confidence": "high",
    },
    "urethane_foam_management_required": {
        "item": "urethane_foam_management",
        "category": "labor",
        "confidence": "high",
    },
    "undercoating_application_required": {
        "item": "undercoating_application",
        "category": "materials_and_labor",
        "confidence": "high",
    },
}


def infer_supplement_candidates(procedure: dict, structure: dict | None = None) -> dict:
    candidates = []

    for dep in procedure.get("dependencies", []):
        dep_type = dep["type"]
        if dep_type in ("replace_component", "replace_if_sectioned"):
            candidates.append({
                "item": dep["target"],
                "reason": dep_type,
                "category": "parts",
                "confidence": "high" if dep_type == "replace_component" else "conditional",
            })

    for req in get_corrosion_requirements(procedure):
        mapping = _CORROSION_ITEMS.get(req)
        if mapping:
            candidates.append({**mapping, "reason": f"corrosion_requirement: {req}"})

    sectioning = get_sectioning_locations(procedure)
    if sectioning:
        candidates.append({
            "item": "sectioning_labor",
            "reason": f"{len(sectioning)} sectioning location(s) identified",
            "category": "labor",
            "confidence": "high",
        })

    if structure:
        uhss_components = get_uhss_components(structure)
        if uhss_components and "mig_brazing" in get_joining_methods(procedure):
            candidates.append({
                "item": "mig_brazing_labor",
                "reason": f"UHSS material present ({len(uhss_components)} component(s))",
                "category": "labor",
                "confidence": "high",
            })

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "supplement_candidates": candidates,
        "total": len(candidates),
        "by_category": {
            "parts": [c for c in candidates if c["category"] == "parts"],
            "materials_and_labor": [c for c in candidates if c["category"] == "materials_and_labor"],
            "labor": [c for c in candidates if c["category"] == "labor"],
        },
    }
