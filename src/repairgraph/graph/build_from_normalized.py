import re

from repairgraph.taxonomy.aliases import resolve_alias


def canonical_id(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return resolve_alias(cleaned)


def _add_node(nodes_by_id: dict, node_id: str, node_type: str, label: str | None = None, **attrs):
    if node_id not in nodes_by_id:
        node = {
            "id": node_id,
            "type": node_type,
            "label": label or node_id.replace("_", " "),
        }
        node.update(attrs)
        nodes_by_id[node_id] = node
    return nodes_by_id[node_id]


def _add_edge(edges: list, source: str, target: str, relationship: str):
    edges.append({"source": source, "target": target, "relationship": relationship})


def build_graph_from_normalized(procedure: dict, structure: dict | None = None) -> dict:
    nodes_by_id: dict = {}
    edges: list = []

    model = procedure.get("model", "unknown")
    oem = procedure.get("oem", "unknown")
    year = procedure.get("year", 0)
    operation = procedure.get("operation", "repair_operation")

    op_id = canonical_id(f"{year}_{model}_{operation}")
    _add_node(
        nodes_by_id,
        op_id,
        "operation",
        f"{year} {oem} {model} — {operation.replace('_', ' ').title()}",
        oem=oem,
        year=year,
        model=model,
    )

    for method in procedure.get("joining_methods", []):
        method_id = canonical_id(method)
        _add_node(nodes_by_id, method_id, "joining_method", method.replace("_", " "))
        _add_edge(edges, op_id, method_id, "uses_joining_method")

    for dep in procedure.get("dependencies", []):
        target = dep["target"]
        target_id = canonical_id(target)
        _add_node(nodes_by_id, target_id, "structure_node", target.replace("_", " "))
        _add_edge(edges, op_id, target_id, dep["type"])

    for req in procedure.get("corrosion_requirements", []):
        req_id = canonical_id(req)
        _add_node(nodes_by_id, req_id, "corrosion_requirement", req.replace("_", " "))
        _add_edge(edges, op_id, req_id, "requires_corrosion_protection")

    for loc in procedure.get("sectioning_locations", []):
        zone = loc.get("zone", "unknown_zone")
        loc_id = canonical_id(f"section_{zone}")
        _add_node(
            nodes_by_id,
            loc_id,
            "sectioning_location",
            f"Section: {zone.replace('_', ' ')}",
            description=loc.get("description", ""),
        )
        _add_edge(edges, op_id, loc_id, "sections_at")

    for rel in procedure.get("spatial_relationships", []):
        src_id = canonical_id(rel["source"])
        tgt_id = canonical_id(rel["target"])
        relationship = rel["relationship"]

        _add_node(nodes_by_id, src_id, "structure_node", rel["source"].replace("_", " "))
        _add_node(nodes_by_id, tgt_id, "structure_node", rel["target"].replace("_", " "))
        _add_edge(edges, src_id, tgt_id, relationship)

    if structure:
        for material in structure.get("materials", []):
            component = material["component"]
            comp_id = canonical_id(component)

            classification = material.get("classification", "unknown")
            strength = material.get("tensile_strength_mpa")
            label = f"{component.replace('_', ' ')} ({classification}"
            if strength:
                label += f", {strength} MPa"
            label += ")"

            _add_node(
                nodes_by_id,
                comp_id,
                "material_spec",
                label,
                classification=classification,
                tensile_strength_mpa=strength,
                thickness_mm=material.get("thickness_mm"),
                zinc_plated=material.get("zinc_plated"),
            )

            structure_op_id = op_id
            if comp_id in nodes_by_id:
                _add_edge(edges, structure_op_id, comp_id, "uses_material")

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": edges,
        "meta": {
            "oem": oem,
            "year": year,
            "model": model,
            "operation": operation,
        },
    }


def build_multi_vehicle_graph(procedures_and_structures: list[tuple[dict, dict | None]]) -> dict:
    all_nodes_by_id: dict = {}
    all_edges: list = []
    metas: list = []

    for procedure, structure in procedures_and_structures:
        graph = build_graph_from_normalized(procedure, structure)

        for node in graph["nodes"]:
            if node["id"] not in all_nodes_by_id:
                all_nodes_by_id[node["id"]] = node

        all_edges.extend(graph["edges"])
        metas.append(graph["meta"])

    component_to_operations: dict = {}
    for edge in all_edges:
        if edge["relationship"] in ("replace_component", "replace_if_sectioned", "inspect_if_damaged"):
            component = edge["target"]
            operation = edge["source"]
            component_to_operations.setdefault(component, []).append(operation)

    for component, operations in component_to_operations.items():
        if len(operations) > 1:
            for i in range(len(operations)):
                for j in range(i + 1, len(operations)):
                    all_edges.append({
                        "source": operations[i],
                        "target": operations[j],
                        "relationship": "shares_component",
                        "shared_component": component,
                    })

    return {
        "nodes": list(all_nodes_by_id.values()),
        "edges": all_edges,
        "meta": {
            "type": "multi_vehicle_graph",
            "procedures": metas,
        },
    }
