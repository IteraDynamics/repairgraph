from pathlib import Path
import json

from repairgraph.graph.export_graph import build_graph


EXTRACTED_DIR = Path("data/extracted")


def load_draft(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def export_graph(draft_path: Path, output_name: str):
    draft = load_draft(draft_path)

    graph = build_graph(draft)

    output_path = EXTRACTED_DIR / f"{output_name}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    return output_path


if __name__ == "__main__":
    draft_path = EXTRACTED_DIR / "honda_crv_quarter_draft.json"

    output_path = export_graph(
        draft_path,
        "honda_crv_quarter_graph",
    )

    print(f"Graph exported to: {output_path}")
