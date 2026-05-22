from pathlib import Path
import json

from repairgraph.plan import build_repair_plan
from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)


EXTRACTED_DIR = Path("data/extracted")


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def export_repair_plan(
    *,
    oem: str = "Honda",
    year: int = 2025,
    model: str = "Accord",
    output_dir: Path = EXTRACTED_DIR,
) -> Path:
    procedure = load_procedure(oem, year, model)
    structure = load_vehicle_structure(oem, year, model)
    corpus = _corpus_without(model)

    plan = build_repair_plan(procedure, structure, corpus)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{oem.lower()}_{model.lower().replace(' ', '_')}_repair_plan.json"

    output_path.write_text(
        json.dumps(plan, indent=2),
        encoding="utf-8",
    )

    return output_path


def main():
    output_path = export_repair_plan()
    print(f"Repair plan exported to: {output_path}")


if __name__ == "__main__":
    main()
