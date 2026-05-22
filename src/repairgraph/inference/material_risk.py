from repairgraph.evidence import build_evidence
from repairgraph.query.query_procedures import get_joining_methods


UHSS_THRESHOLD_MPA = 980

_UHSS_IMPLICATION = (
    "UHSS material detected. Verify OEM-specified joining method for adjacent joins "
    "before repair planning or QA signoff."
)

_HSS_IMPLICATION = (
    "HSS material detected. Confirm OEM weld/joining compatibility before proceeding."
)


def surface_material_risks(procedure: dict, structure: dict) -> dict:
    joining_methods = get_joining_methods(procedure)
    mig_brazing_present = "mig_brazing" in joining_methods

    risks = []

    for material in structure.get("materials", []):
        strength = material.get("tensile_strength_mpa", 0)
        classification = material.get("classification", "")
        component = material["component"]

        if classification == "UHSS" or strength >= UHSS_THRESHOLD_MPA:
            evidence = build_evidence(
                source_type="normalized_structure",
                basis=[
                    "material_strength_at_or_above_uhss_threshold",
                    "vehicle_structure_material_map",
                ],
                confidence="medium",
                interpretation="advisory",
            )

            risk_item = {
                "component": component,
                "classification": classification,
                "tensile_strength_mpa": strength,
                "risk": "uhss_joining_constraint",
                "advisory": _UHSS_IMPLICATION,
                "confidence": evidence["confidence"],
                "basis": evidence["basis"],
                "evidence": evidence,
                "mig_brazing_in_procedure": mig_brazing_present,
            }
            if not mig_brazing_present:
                risk_item["gap"] = "mig_brazing_not_listed_in_normalized_procedure"
                risk_item["gap_advisory"] = (
                    "UHSS material is present but MIG brazing is not listed in the normalized "
                    "procedure object. Verify the source procedure and joining instructions."
                )
            risks.append(risk_item)

        elif strength >= 590:
            evidence = build_evidence(
                source_type="normalized_structure",
                basis=[
                    "hss_material_strength_detected",
                    "vehicle_structure_material_map",
                ],
                confidence="medium",
                interpretation="advisory",
            )

            risks.append({
                "component": component,
                "classification": classification,
                "tensile_strength_mpa": strength,
                "risk": "hss_joining_awareness",
                "advisory": _HSS_IMPLICATION,
                "confidence": evidence["confidence"],
                "basis": evidence["basis"],
                "evidence": evidence,
            })

    zinc_components = [
        m["component"]
        for m in structure.get("materials", [])
        if m.get("zinc_plated")
    ]

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "material_risks": risks,
        "zinc_plated_components": zinc_components,
        "uhss_component_count": sum(
            1 for r in risks if r["risk"] == "uhss_joining_constraint"
        ),
        "interpretation_note": (
            "Material-risk outputs are advisory flags derived from normalized structure data. "
            "They should be verified against the applicable OEM procedure before operational use."
        ),
    }
