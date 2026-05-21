from pathlib import Path
import json

import jsonschema


NORMALIZED_DIR = Path("data/normalized")
SCHEMAS_DIR = Path("schemas")

_schema_cache: dict[str, dict] = {}


def _load_schema(filename: str) -> dict:
    if filename not in _schema_cache:
        path = SCHEMAS_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            _schema_cache[filename] = json.load(f)
    return _schema_cache[filename]


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_repair_procedure(data: dict):
    schema = _load_schema("repair_procedure.schema.json")
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f"Schema validation failed: {e.message}") from e


def validate_vehicle_structure(data: dict):
    schema = _load_schema("vehicle_structure_schema.json")
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f"Schema validation failed: {e.message}") from e


def main():
    for path in sorted(NORMALIZED_DIR.rglob("*.json")):
        data = load_json(path)

        if "operation" in data:
            validate_repair_procedure(data)
            print(f"[OK] repair procedure: {path}")

        elif "domain" in data:
            validate_vehicle_structure(data)
            print(f"[OK] vehicle structure: {path}")


if __name__ == "__main__":
    main()
