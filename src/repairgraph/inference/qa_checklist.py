from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_corrosion_requirements,
)


def generate_qa_checklist(
    procedure: dict,
    structure: dict | None = None,
    corpus: list[dict] | None = None,
) -> dict:
    """
    Produce a structured QA checklist for a repair procedure.

    Combines material compliance, joining verification, component
    replacement confirmation, corrosion protection, dimensional
    verification, and corpus-gap completeness checks.
    """
    checks = []

    if structure:
        from repairgraph.inference.material_risk import surface_material_risks
        risks = surface_material_risks(procedure, structure)
        for risk in risks["material_risks"]:
            if risk["risk"] == "uhss_joining_constraint":
                checks.append({
                    "category": "material_compliance",
                    "priority": "critical",
                    "check": (
                        f"Verify MIG brazing used at joins adjacent to "
                        f"{risk['component'].replace('_', ' ')} "
                        f"({risk['tensile_strength_mpa']} MPa UHSS)"
                    ),
                    "pass_condition": "MIG brazing confirmed at all joins adjacent to this component",
                    "gap_detected": "gap" in risk,
                })

    for method in get_joining_methods(procedure):
        checks.append({
            "category": "joining_compliance",
            "priority": "high",
            "check": f"Verify {method.replace('_', ' ')} applied at all specified locations",
            "pass_condition": "Join confirmed and meets OEM specification",
        })

    for dep in procedure.get("dependencies", []):
        target_label = dep["target"].replace("_", " ")
        if dep["type"] == "replace_component":
            checks.append({
                "category": "component_replacement",
                "priority": "high",
                "check": f"Verify {target_label} replaced with new OEM part",
                "pass_condition": "New OEM component installed and documented",
            })
        elif dep["type"] == "replace_if_sectioned":
            checks.append({
                "category": "component_replacement",
                "priority": "medium",
                "check": f"If sectioned: verify {target_label} replaced",
                "pass_condition": "Component replaced, or confirmed intact and undamaged",
                "conditional": True,
            })
        elif dep["type"] == "inspect_if_damaged":
            checks.append({
                "category": "inspection",
                "priority": "medium",
                "check": f"Confirm {target_label} inspected for damage",
                "pass_condition": "Component inspected and result documented",
            })

    for req in get_corrosion_requirements(procedure):
        checks.append({
            "category": "corrosion_protection",
            "priority": "high",
            "check": f"Verify {req.replace('_', ' ')} completed",
            "pass_condition": "Application confirmed per OEM corrosion protection specification",
        })

    for note in procedure.get("repair_notes", []):
        if any(kw in note.lower() for kw in ("check body", "confirm", "dimension", "verify")):
            checks.append({
                "category": "dimensional_verification",
                "priority": "high",
                "check": note,
                "pass_condition": "Confirmed within OEM tolerance before final welding",
            })

    if corpus:
        from repairgraph.inference.missing_operations import detect_missing_operations
        gaps = detect_missing_operations(procedure, corpus)
        for gap in gaps["missing_components"]:
            checks.append({
                "category": "completeness",
                "priority": "high" if gap["confidence"] == "high" else "medium",
                "check": (
                    f"Confirm whether {gap['component'].replace('_', ' ')} requires attention "
                    f"(present in {gap['corpus_frequency']:.0%} of similar procedures)"
                ),
                "pass_condition": "Component explicitly addressed or documented as not applicable",
                "corpus_gap": True,
            })

    by_category: dict[str, list] = {}
    by_priority: dict[str, list] = {"critical": [], "high": [], "medium": []}
    for check in checks:
        by_category.setdefault(check["category"], []).append(check)
        by_priority.setdefault(check.get("priority", "medium"), []).append(check)

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "operation": procedure.get("operation"),
        "total_checks": len(checks),
        "checks": checks,
        "by_category": by_category,
        "by_priority": by_priority,
    }
