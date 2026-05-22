import json
from pathlib import Path
import pytest
from repairgraph.validate import validate_repair_procedure, validate_vehicle_structure


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


PROCEDURE_PATHS = list(
    Path("data/normalized").rglob("repair_procedure_*.json")
)

STRUCTURE_PATHS = list(
    Path("data/normalized").rglob("vehicle_structure.json")
)


@pytest.mark.parametrize("path", PROCEDURE_PATHS, ids=[p.parent.name for p in PROCEDURE_PATHS])
def test_validate_repair_procedure(path):
    data = load_json(path)
    validate_repair_procedure(data)


@pytest.mark.parametrize("path", STRUCTURE_PATHS, ids=[p.parent.name for p in STRUCTURE_PATHS])
def test_validate_vehicle_structure(path):
    data = load_json(path)
    validate_vehicle_structure(data)
