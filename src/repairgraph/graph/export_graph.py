import re


OPERATION_NODE_ID = "repair_operation"


def canonical_id(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def add_node(nodes_by_id: dict, node_id: str, node_type: str, label: str | None = None):
    if node_id not in nodes_by_id:
        nodes_by_id[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label or node_id,
        }

    return nodes_by_id[node_id]


def build_graph(draft: dict) -> dict:
    nodes_by_id = {}
    edges = []

    add_node(
        nodes_by_id,
        OPERATION_NODE_ID,
        "operation",
        "Repair Operation",
    )

    for structure_node in draft.get("structure_nodes", []):
        label = structure_node["phrase"]
        node_id = canonical_id(label)

        add_node(
            nodes_by_id,
            node_id,
            structure_node["class"],
            label,
        )

    for dependency in draft.get("typed_dependencies", []):
        target = dependency["target"]
        target_id = canonical_id(target)

        add_node(
            nodes_by_id,
            target_id,
            "dependency_target",
            target.replace("_", " "),
        )

        edges.append(
            {
                "source": OPERATION_NODE_ID,
                "target": target_id,
                "relationship": dependency["type"],
            }
        )

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": edges,
    }
