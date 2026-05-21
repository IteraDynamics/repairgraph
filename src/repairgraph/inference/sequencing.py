from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_inspection_dependencies,
    get_corrosion_requirements,
    get_sectioning_locations,
    get_dependencies_by_type,
)


_VERIFICATION_KEYWORDS = ("check body", "confirm", "dimension", "verify")


def build_operation_sequence(procedure: dict) -> dict:
    """
    Infer a phased operation order from a normalized procedure.

    Phases follow the natural repair flow:
      1  Pre-repair inspection
      2  Sectioning preparation   (if applicable)
      3  Component replacement
      4  Panel installation and joining
      5  Corrosion protection
      6  Post-repair verification
    """
    phases = []

    inspections = get_inspection_dependencies(procedure)
    if inspections:
        phases.append({
            "phase": 1,
            "name": "pre_repair_inspection",
            "label": "Pre-Repair Inspection",
            "items": [
                {"action": "inspect_if_damaged", "target": c}
                for c in inspections
            ],
        })

    sectioning = get_sectioning_locations(procedure)
    conditional = get_dependencies_by_type(procedure, "replace_if_sectioned")
    if sectioning:
        items = [
            {
                "action": "select_cut_position",
                "zone": loc["zone"],
                "description": loc.get("description", ""),
            }
            for loc in sectioning
        ]
        items += [
            {"action": "replace_if_sectioned", "target": c}
            for c in conditional
        ]
        phases.append({
            "phase": 2,
            "name": "sectioning_preparation",
            "label": "Sectioning Preparation",
            "items": items,
        })

    replacements = get_replacement_dependencies(procedure)
    if replacements:
        phases.append({
            "phase": 3,
            "name": "component_replacement",
            "label": "Component Removal and Replacement",
            "items": [
                {"action": "replace_component", "target": c}
                for c in replacements
            ],
        })

    joining_methods = get_joining_methods(procedure)
    phases.append({
        "phase": 4,
        "name": "panel_installation_and_joining",
        "label": "Panel Installation and Joining",
        "items": [
            {"action": "apply_joining_method", "method": m}
            for m in joining_methods
        ],
    })

    corrosion = get_corrosion_requirements(procedure)
    if corrosion:
        phases.append({
            "phase": 5,
            "name": "corrosion_protection",
            "label": "Corrosion Protection",
            "items": [
                {"action": "apply_corrosion_protection", "requirement": r}
                for r in corrosion
            ],
        })

    verification_notes = [
        n for n in procedure.get("repair_notes", [])
        if any(kw in n.lower() for kw in _VERIFICATION_KEYWORDS)
    ]
    if verification_notes:
        phases.append({
            "phase": 6,
            "name": "post_repair_verification",
            "label": "Post-Repair Verification",
            "items": [{"action": "verify", "note": n} for n in verification_notes],
        })

    for i, phase in enumerate(phases, start=1):
        phase["phase"] = i

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "operation": procedure.get("operation"),
        "phases": phases,
        "total_phases": len(phases),
    }
