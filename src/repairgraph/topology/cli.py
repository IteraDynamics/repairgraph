from pathlib import Path
import json

from repairgraph.query.loader import (
    load_all_procedures,
    load_all_vehicle_structures,
)
from repairgraph.topology.builder import build_topology_graph
from repairgraph.topology.export_json import topology_to_dict
from repairgraph.topology.export_mermaid import (
    build_adjacency_mermaid,
    build_operation_overlay_mermaid,
)
from repairgraph.topology.export_visualization import build_visualization_payload


OUTPUT_DIR = Path("data/extracted/topology")


def _slug(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def main() -> None:
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()
    structure_by_key = {
        (s.get("oem"), s.get("year"), s.get("model")): s
        for s in structures
    }

    exported = []

    for procedure in procedures:
        key = (
            procedure.get("oem"),
            procedure.get("year"),
            procedure.get("model"),
        )
        structure = structure_by_key.get(key)
        topology = build_topology_graph(procedure, structure)

        prefix = f"{_slug(procedure.get('oem', 'unknown'))}_{procedure.get('year')}_{_slug(procedure.get('model', 'unknown'))}"

        topology_json_path = OUTPUT_DIR / f"{prefix}_topology.json"
        adjacency_mermaid_path = OUTPUT_DIR / f"{prefix}_adjacency.mmd"
        overlay_mermaid_path = OUTPUT_DIR / f"{prefix}_operation_overlay.mmd"
        visualization_path = OUTPUT_DIR / f"{prefix}_visualization.json"

        _write_json(topology_json_path, topology_to_dict(topology))
        _write_text(adjacency_mermaid_path, build_adjacency_mermaid(topology))
        _write_text(overlay_mermaid_path, build_operation_overlay_mermaid(topology))
        _write_json(visualization_path, build_visualization_payload(topology))

        exported.append({
            "model": procedure.get("model"),
            "topology_json": str(topology_json_path),
            "adjacency_mermaid": str(adjacency_mermaid_path),
            "operation_overlay_mermaid": str(overlay_mermaid_path),
            "visualization_payload": str(visualization_path),
            "zones": len(topology.zones),
            "relationships": len(topology.zone_relationships),
            "operation_stages": len(topology.operation_stages),
        })

    print("RepairGraph topology exports")
    print("---------------------------")
    for item in exported:
        print(
            f"{item['model']}: "
            f"zones={item['zones']} "
            f"relationships={item['relationships']} "
            f"stages={item['operation_stages']}"
        )
        print(f"  topology:      {item['topology_json']}")
        print(f"  adjacency:     {item['adjacency_mermaid']}")
        print(f"  overlay:       {item['operation_overlay_mermaid']}")
        print(f"  visualization: {item['visualization_payload']}")


if __name__ == "__main__":
    main()
