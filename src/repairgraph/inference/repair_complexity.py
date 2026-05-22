from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_corrosion_requirements,
    get_sectioning_locations,
    get_uhss_components,
)


JOINING_METHOD_WEIGHTS = {
    "mig_brazing": 3,
    "mag_plug_weld": 2,
    "hemming": 2,
    "spot_weld": 1,
    "adhesive_bonding": 1,
    "urethane_foam_retention": 1,
}

TIER_THRESHOLDS = [
    (0, 4, "low"),
    (5, 9, "moderate"),
    (10, 14, "high"),
    (15, float("inf"), "critical"),
]


def _tier(score: int) -> str:
    for low, high, label in TIER_THRESHOLDS:
        if low <= score <= high:
            return label
    return "critical"


def score_repair_complexity(procedure: dict, structure: dict | None = None) -> dict:
    flags = []

    joining_score = 0
    for method in get_joining_methods(procedure):
        joining_score += JOINING_METHOD_WEIGHTS.get(method, 1)
        if method == "mig_brazing":
            flags.append("mig_brazing_required")

    replacements = get_replacement_dependencies(procedure)
    dep_score = len(replacements)
    if len(replacements) >= 4:
        flags.append("high_replacement_count")

    sectioning = get_sectioning_locations(procedure)
    sect_score = len(sectioning) * 2
    if sectioning:
        flags.append("sectioning_required")

    corrosion = get_corrosion_requirements(procedure)
    corr_score = len(corrosion)

    if structure and get_uhss_components(structure):
        flags.append("uhss_material_present")

    total = joining_score + dep_score + sect_score + corr_score

    return {
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "score": total,
        "tier": _tier(total),
        "breakdown": {
            "joining_methods": joining_score,
            "replacement_dependencies": dep_score,
            "sectioning_locations": sect_score,
            "corrosion_requirements": corr_score,
        },
        "risk_flags": sorted(set(flags)),
    }
