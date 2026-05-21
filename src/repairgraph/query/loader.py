from pathlib import Path
import json


NORMALIZED_DIR = Path("data/normalized")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_procedures() -> list[dict]:
    procedures = []
    for path in sorted(NORMALIZED_DIR.rglob("repair_procedure_*.json")):
        procedures.append(load_json(path))
    return procedures


def load_all_vehicle_structures() -> list[dict]:
    structures = []
    for path in sorted(NORMALIZED_DIR.rglob("vehicle_structure.json")):
        structures.append(load_json(path))
    return structures


def load_procedure(oem: str, year: int, model: str) -> dict | None:
    model_slug = model.lower().replace("-", "_").replace(" ", "_")
    path = NORMALIZED_DIR / oem.lower() / f"{year}_{model_slug}" / "repair_procedure_quarter_panel.json"
    if path.exists():
        return load_json(path)
    return None


def load_vehicle_structure(oem: str, year: int, model: str) -> dict | None:
    model_slug = model.lower().replace("-", "_").replace(" ", "_")
    path = NORMALIZED_DIR / oem.lower() / f"{year}_{model_slug}" / "vehicle_structure.json"
    if path.exists():
        return load_json(path)
    return None
