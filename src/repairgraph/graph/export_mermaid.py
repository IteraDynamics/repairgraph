from pathlib import Path
import json


EXTRACTED_DIR = Path("data/extracted")


def load_graph(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_node_label(node_id: str, nodes_by_id: dict) -> str:
    node = nodes_by_id.get(node_id, {})
    label = node.get("label", node_id)
    return label.replace('"', "'")


def build_mermaid(graph: dict) -> str:
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}

    lines = ["graph TD"]

    for edge in graph.get("edges", []):
        source = edge["source"]
        target = edge["target"]
        relationship = edge["relationship"]

        source_label = format_node_label(source, nodes_by_id)
        target_label = format_node_label(target, nodes_by_id)

        lines.append(
            f'  {source}["{source_label}"] -->|{relationship}| {target}["{target_label}"]'
        )

    return "\n".join(lines) + "\n"


def export_mermaid(graph_path: Path, output_name: str) -> Path:
    graph = load_graph(graph_path)

    mermaid = build_mermaid(graph)

    output_path = EXTRACTED_DIR / f"{output_name}.mmd"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(mermaid)

    return output_path


def main():
    graph_path = EXTRACTED_DIR / "honda_crv_quarter_graph.json"

    output_path = export_mermaid(
        graph_path,
        "honda_crv_quarter_graph",
    )

    print(f"Mermaid graph exported to: {output_path}")


if __name__ == "__main__":
    main()
