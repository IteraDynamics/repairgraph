from repairgraph.query.query_procedures import get_joining_methods


UHSS_THRESHOLD_MPA = 980

_UHSS_IMPLICATION = (
    "Spot welding prohibited adjacent to this component. "
    "MIG brazing required for flange joins."
)

_HSS_IMPLICATION = (
    "Confirm weld compatibility before proceeding. "
    "MAG plug weld or MIG brazing may be required at joins."
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
            risk_item = {
                "component": component,
                "classification": classification,
                "tensile_strength_mpa": strength,
                "risk": "uhss_joining_constraint",
                "implication": _UHSS_IMPLICATION,
                "mig_brazing_in_procedure": mig_brazing_present,
            }
            if not mig_brazing_present:
                risk_item["gap"] = "mig_brazing_not_listed_in_procedure"
            risks.append(risk_item)

        elif strength >= 590:
            risks.append({
                "component": component,
                "classification": classification,
                "tensile_strength_mpa": strength,
                "risk": "hss_joining_awareness",
                "implication": _HSS_IMPLICATION,
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
    }
