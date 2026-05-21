def build_graph(draft: dict) -> dict:
    nodes = []
    edges = []

    for structure_node in draft.get("structure_nodes", []):
        node_id = structure_node["phrase"]

        nodes.append(
            {
                "id": node_id,
                "type": structure_node["class"],
            }
        )

    for dependency in draft.get("typed_dependencies", []):
        target = dependency["target"]

        nodes.append(
            {
                "id": target,
                "type": "dependency_target",
            }
        )

        edges.append(
            {
                "source": "repair_operation",
                "target": target,
                "relationship": dependency["type"],
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
    }
