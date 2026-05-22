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
    Produce a structured advisory QA checklist for a repair procedure.

    Combines material awareness, joining verification, component replacement
    confirmation, corrosion protection, dimensional verification, and corpus-gap
    review items. Outputs should be verified against the applicable OEM source.
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
                        f"Verify OEM-specified joining method for joins adjacent to "
                        f"{risk['component'].replace('_', ' ')} "
                        f"({risk['tensile_strength_mpa']} MPa UHSS)"
                    ),
                    "pass_condition": "OEM-specified joining method confirmed and documented",
                    "gap_detected": "gap" in risk,
                    "basis": risk.get("basis", []),
                    "confidence": risk.get("confidence", "medium"),
                    "advisory": risk.get("advisory"),
                })

    for method in get_joining_methods(procedure):
        checks.append({
            "category": "joining_compliance",
            "priority": "high",
            "check": f"Verify {method.replace('_', ' ')} where specified by the OEM procedure",
            "pass_condition": "Join confirmed against OEM procedure and documented",
        })

    for dep in procedure.get("dependencies", []):
        target_label = dep["target"].replace("_", " ")
        if dep["type"] == "replace_component":
            checks.append({
                "category": "component_replacement",
                "priority": "high",
                "check": f"Verify {target_label} replacement requirement against the OEM procedure",
                "pass_condition": "Component replacement completed or documented as not applicable per OEM procedure",
            })
        elif dep["type"] == "replace_if_sectioned":
            checks.append({
                "category": "component_replacement",
                "priority": "medium",
                "check": f"If sectioned: verify whether {target_label} replacement applies",
                "pass_condition": "Component replaced, or confirmed intact/not applicable and documented",
                "conditional": True,
            })
        elif dep["type"] == "inspect_if_damaged":
            checks.append({
                "category": "inspection",
                "priority": "medium",
                "check": f"Confirm {target_label} inspected for damage where procedure indicates",
                "pass_condition": "Component inspected and result documented",
            })

    for req in get_corrosion_requirements(procedure):
        checks.append({
            "category": "corrosion_protection",
            "priority": "high",
            "check": f"Verify {req.replace('_', ' ')} where specified by the OEM procedure",
            "pass_condition": "Application confirmed against OEM corrosion protection instructions",
        })

    for note in procedure.get("repair_notes", []):
        if any(kw in note.lower() for kw in ("check body", "confirm", "dimension", "verify")):
            checks.append({
                "category": "dimensional_verification",
                "priority": "high",
                "check": note,
                "pass_condition": "Confirmed against OEM repair procedure before final welding",
            })

    if corpus:
        from repairgraph.inference.missing_operations import detect_missing_operations
        gaps = detect_missing_operations(procedure, corpus)
        for gap in gaps["corpus_gap_components"]:
            checks.append({
                "category": "completeness",
                "priority": "high" if gap["confidence"] == "high" else "medium",
                "check": (
                    f"Review whether {gap['component'].replace('_', ' ')} is applicable "
                    f"(present in {gap['corpus_frequency']:.0%} of comparable normalized procedures)"
                ),
                "pass_condition": "Component explicitly addressed or documented as not applicable",
                "corpus_gap": True,
                "confidence": gap["confidence"],
                "advisory": gap["advisory"],
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
        "interpretation_note": (
            "QA checklist outputs are advisory review items derived from normalized RepairGraph data. "
            "They should be verified against the applicable OEM procedure before operational use."
        ),
    }
