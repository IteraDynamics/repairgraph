from pathlib import Path
import json

from repairgraph.query.loader import (
    load_all_procedures,
    load_all_vehicle_structures,
    load_procedure,
    load_vehicle_structure,
)
from repairgraph.graph.build_from_normalized import (
    build_graph_from_normalized,
    build_multi_vehicle_graph,
)
from repairgraph.graph.export_mermaid import build_mermaid


OUTPUT_DIR = Path("data/extracted")


def export_single_vehicle_graph(oem: str, year: int, model: str) -> Path:
    procedure = load_procedure(oem, year, model)
    structure = load_vehicle_structure(oem, year, model)

    if not procedure:
        raise FileNotFoundError(f"No procedure found for {year} {oem} {model}")

    graph = build_graph_from_normalized(procedure, structure)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_slug = model.lower().replace("-", "_").replace(" ", "_")
    output_path = OUTPUT_DIR / f"honda_{model_slug}_normalized_graph.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    return output_path


def export_multi_vehicle_graph() -> Path:
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    structure_by_model = {s["model"]: s for s in structures}

    pairs = [
        (proc, structure_by_model.get(proc["model"]))
        for proc in procedures
    ]

    graph = build_multi_vehicle_graph(pairs)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "honda_multi_vehicle_graph.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    return output_path


def export_multi_vehicle_mermaid() -> Path:
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    structure_by_model = {s["model"]: s for s in structures}

    pairs = [
        (proc, structure_by_model.get(proc["model"]))
        for proc in procedures
    ]

    graph = build_multi_vehicle_graph(pairs)

    mermaid = build_mermaid(graph)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "honda_multi_vehicle_graph.mmd"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(mermaid)

    return output_path


def main():
    for model in ["CR-V", "Accord", "Civic", "Pilot", "Odyssey"]:
        try:
            path = export_single_vehicle_graph("Honda", 2025, model)
            print(f"Exported: {path}")
        except FileNotFoundError as e:
            print(f"Skipped: {e}")

    path = export_multi_vehicle_graph()
    print(f"Multi-vehicle graph exported to: {path}")

    path = export_multi_vehicle_mermaid()
    print(f"Multi-vehicle Mermaid exported to: {path}")


if __name__ == "__main__":
    main()
