from pathlib import Path
import json


NORMALIZED_DIR = Path("data/normalized")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_required_fields(data: dict, required_fields: list[str]):
    missing = [field for field in required_fields if field not in data]

    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def validate_repair_procedure(data: dict):
    validate_required_fields(
        data,
        ["oem", "year", "model", "operation", "operation_family"]
    )


def validate_vehicle_structure(data: dict):
    validate_required_fields(
        data,
        ["oem", "year", "model", "domain"]
    )


if __name__ == "__main__":
    for path in NORMALIZED_DIR.rglob("*.json"):
        data = load_json(path)

        if "operation" in data:
            validate_repair_procedure(data)
            print(f"[OK] repair procedure: {path}")

        elif "domain" in data:
            validate_vehicle_structure(data)
            print(f"[OK] vehicle structure: {path}")
