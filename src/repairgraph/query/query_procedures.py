def get_joining_methods(procedure: dict) -> list[str]:
    return procedure.get("joining_methods", [])


def get_dependencies(procedure: dict) -> list[dict]:
    return procedure.get("dependencies", [])


def get_dependencies_by_type(procedure: dict, dep_type: str) -> list[str]:
    return [
        dep["target"]
        for dep in procedure.get("dependencies", [])
        if dep["type"] == dep_type
    ]


def get_replacement_dependencies(procedure: dict) -> list[str]:
    return [
        dep["target"]
        for dep in procedure.get("dependencies", [])
        if dep["type"] in ("replace_component", "replace_if_sectioned")
    ]


def get_inspection_dependencies(procedure: dict) -> list[str]:
    return get_dependencies_by_type(procedure, "inspect_if_damaged")


def get_corrosion_requirements(procedure: dict) -> list[str]:
    return procedure.get("corrosion_requirements", [])


def get_sectioning_locations(procedure: dict) -> list[dict]:
    return procedure.get("sectioning_locations", [])


def get_materials(structure: dict) -> list[dict]:
    return structure.get("materials", [])


def get_structure_nodes(structure: dict) -> list[str]:
    return structure.get("structure_nodes", [])


def get_uhss_components(structure: dict) -> list[dict]:
    return [
        m for m in structure.get("materials", [])
        if m.get("classification") == "UHSS"
    ]


def get_hss_components(structure: dict) -> list[dict]:
    return [
        m for m in structure.get("materials", [])
        if m.get("classification") == "HSS"
    ]
