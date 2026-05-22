from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_inspection_dependencies,
    get_corrosion_requirements,
    get_uhss_components,
)


def _proc_label(procedure: dict) -> str:
    return f"{procedure['year']} {procedure['oem']} {procedure['model']}"


def find_by_joining_method(procedures: list[dict], method: str) -> list[dict]:
    return [p for p in procedures if method in get_joining_methods(p)]


def find_by_component(procedures: list[dict], component: str) -> list[dict]:
    results = []
    for proc in procedures:
        all_targets = (
            get_replacement_dependencies(proc)
            + get_inspection_dependencies(proc)
        )
        spatial = [
            rel["target"]
            for rel in proc.get("spatial_relationships", [])
        ] + [
            rel["source"]
            for rel in proc.get("spatial_relationships", [])
        ]
        if component in all_targets or component in spatial:
            results.append(proc)
    return results


def find_by_corrosion_requirement(procedures: list[dict], requirement: str) -> list[dict]:
    return [p for p in procedures if requirement in get_corrosion_requirements(p)]


def compare_procedures(proc1: dict, proc2: dict) -> dict:
    methods1 = set(get_joining_methods(proc1))
    methods2 = set(get_joining_methods(proc2))

    replace1 = set(get_replacement_dependencies(proc1))
    replace2 = set(get_replacement_dependencies(proc2))

    inspect1 = set(get_inspection_dependencies(proc1))
    inspect2 = set(get_inspection_dependencies(proc2))

    corrosion1 = set(get_corrosion_requirements(proc1))
    corrosion2 = set(get_corrosion_requirements(proc2))

    return {
        "labels": [_proc_label(proc1), _proc_label(proc2)],
        "joining_methods": {
            "shared": sorted(methods1 & methods2),
            "only_first": sorted(methods1 - methods2),
            "only_second": sorted(methods2 - methods1),
        },
        "replacement_dependencies": {
            "shared": sorted(replace1 & replace2),
            "only_first": sorted(replace1 - replace2),
            "only_second": sorted(replace2 - replace1),
        },
        "inspection_dependencies": {
            "shared": sorted(inspect1 & inspect2),
            "only_first": sorted(inspect1 - inspect2),
            "only_second": sorted(inspect2 - inspect1),
        },
        "corrosion_requirements": {
            "shared": sorted(corrosion1 & corrosion2),
            "only_first": sorted(corrosion1 - corrosion2),
            "only_second": sorted(corrosion2 - corrosion1),
        },
    }


def get_common_components(procedures: list[dict]) -> list[str]:
    if not procedures:
        return []

    component_sets = []
    for proc in procedures:
        components = set(
            get_replacement_dependencies(proc)
            + get_inspection_dependencies(proc)
        )
        component_sets.append(components)

    common = component_sets[0]
    for s in component_sets[1:]:
        common = common & s

    return sorted(common)


def procedures_requiring_uhss_handling(
    procedures: list[dict],
    structures: list[dict],
) -> list[str]:
    structure_by_model = {s["model"]: s for s in structures}

    results = []
    for proc in procedures:
        model = proc["model"]
        structure = structure_by_model.get(model)
        if structure and get_uhss_components(structure):
            results.append(_proc_label(proc))

    return results
