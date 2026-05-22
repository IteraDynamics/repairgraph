from collections import Counter

from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_inspection_dependencies,
    get_corrosion_requirements,
)
from repairgraph.taxonomy.aliases import resolve_alias


def find_corpus_motifs(procedures: list[dict]) -> dict:
    n = len(procedures)
    if n == 0:
        return {"corpus_size": 0}

    component_counts: Counter = Counter()
    joining_counts: Counter = Counter()
    corrosion_counts: Counter = Counter()
    component_by_model: dict[str, set] = {}

    for proc in procedures:
        model = proc.get("model", "unknown")
        components = set(
            resolve_alias(c)
            for c in (
                get_replacement_dependencies(proc)
                + get_inspection_dependencies(proc)
            )
        )
        component_by_model[model] = components

        for c in components:
            component_counts[c] += 1
        for m in get_joining_methods(proc):
            joining_counts[m] += 1
        for r in get_corrosion_requirements(proc):
            corrosion_counts[r] += 1

    universal_components = sorted(c for c, cnt in component_counts.items() if cnt == n)
    universal_joining = sorted(m for m, cnt in joining_counts.items() if cnt == n)
    universal_corrosion = sorted(r for r, cnt in corrosion_counts.items() if cnt == n)

    majority = max(2, int(n * 0.6))

    common_components = [
        {
            "component": c,
            "frequency": cnt / n,
            "models": sorted(m for m, comps in component_by_model.items() if c in comps),
        }
        for c, cnt in sorted(component_counts.items(), key=lambda x: -x[1])
        if cnt >= majority
    ]

    common_joining = [
        {"method": m, "frequency": cnt / n, "count": cnt}
        for m, cnt in sorted(joining_counts.items(), key=lambda x: -x[1])
        if cnt >= majority
    ]

    model_specific = sorted(
        [
            {
                "component": c,
                "model": next(
                    (m for m, comps in component_by_model.items() if c in comps), None
                ),
            }
            for c, cnt in component_counts.items()
            if cnt == 1
        ],
        key=lambda x: (x["model"] or "", x["component"]),
    )

    return {
        "corpus_size": n,
        "universal_components": universal_components,
        "universal_joining_methods": universal_joining,
        "universal_corrosion_requirements": universal_corrosion,
        "common_components": common_components,
        "common_joining_methods": common_joining,
        "model_specific_components": model_specific,
    }
