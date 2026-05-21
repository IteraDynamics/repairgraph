from pathlib import Path
import json

from repairgraph.validate import (
    validate_repair_procedure,
    validate_vehicle_structure,
)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_validate_crv_repair_procedure():
    data = load_json(
        "data/normalized/honda/2025_crv/repair_procedure_quarter_panel.json"
    )

    validate_repair_procedure(data)


def test_validate_crv_vehicle_structure():
    data = load_json(
        "data/normalized/honda/2025_crv/vehicle_structure.json"
    )

    validate_vehicle_structure(data)
