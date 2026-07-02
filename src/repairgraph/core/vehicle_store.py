"""
Lightweight vehicle context store.

Tracks the active vehicle context across HTTP requests by reading/writing
data/active_vehicle.json. No database — just a JSON file on disk.

The active vehicle is the last vehicle whose intake packet was successfully
classified and normalized. All review endpoints use it as their default
vehicle when no explicit OEM/model/year query parameters are supplied.

Listing available vehicles scans data/normalized/ for procedure files,
so the list always reflects what's actually on disk.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_ACTIVE_VEHICLE_PATH = Path("data/active_vehicle.json")
_NORMALIZED_DIR = Path("data/normalized")
_PROCEDURE_FILENAME = "repair_procedure_quarter_panel.json"

_DEMO_VEHICLE = {
    "oem": "Honda",
    "year": 2025,
    "model": "Accord",
    "operation": "quarter_panel_replacement",
    "source": "fixture",
}


@dataclass
class VehicleContext:
    oem: str
    year: int
    model: str
    operation: str = "quarter_panel_replacement"
    normalized_at: str = ""
    intake_id: str = ""
    readiness: str = "unknown"
    source: str = "intake"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VehicleContext":
        return cls(
            oem=d.get("oem", ""),
            year=int(d.get("year", 0)),
            model=d.get("model", ""),
            operation=d.get("operation", "quarter_panel_replacement"),
            normalized_at=d.get("normalized_at", ""),
            intake_id=d.get("intake_id", ""),
            readiness=d.get("readiness", "unknown"),
            source=d.get("source", "intake"),
        )


def get_active_vehicle() -> VehicleContext | None:
    """Return the active vehicle context, or None if not set."""
    try:
        if _ACTIVE_VEHICLE_PATH.exists():
            data = json.loads(_ACTIVE_VEHICLE_PATH.read_text(encoding="utf-8"))
            ctx = VehicleContext.from_dict(data)
            # Only return if we have the minimum required fields
            if ctx.oem and ctx.model and ctx.year:
                return ctx
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def set_active_vehicle(ctx: VehicleContext) -> None:
    """Persist the active vehicle context to disk."""
    _ACTIVE_VEHICLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ACTIVE_VEHICLE_PATH.write_text(
        json.dumps(ctx.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clear_active_vehicle() -> None:
    """Remove the active vehicle context file."""
    if _ACTIVE_VEHICLE_PATH.exists():
        _ACTIVE_VEHICLE_PATH.unlink()


def list_available_vehicles() -> list[dict]:
    """Scan data/normalized/ and return all vehicles that have procedure files.

    Each entry includes whether the vehicle came from a pre-authored fixture
    or from intake normalization (determined by presence of source.intake_id
    in the procedure file).
    """
    vehicles: list[dict] = []
    if not _NORMALIZED_DIR.exists():
        return vehicles

    for proc_path in sorted(_NORMALIZED_DIR.rglob(_PROCEDURE_FILENAME)):
        try:
            proc = json.loads(proc_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        oem = proc.get("oem", "")
        year = proc.get("year", 0)
        model = proc.get("model", "")
        operation = proc.get("operation", "")
        source_meta = proc.get("source", {})
        intake_id = source_meta.get("intake_id", "") if isinstance(source_meta, dict) else ""
        source_type = "intake" if intake_id else "fixture"
        normalized_at = source_meta.get("normalized_at", "") if isinstance(source_meta, dict) else ""

        if oem and model and year:
            vehicles.append({
                "oem": oem,
                "year": year,
                "model": model,
                "operation": operation,
                "source": source_type,
                "intake_id": intake_id or None,
                "normalized_at": normalized_at or None,
                "path": str(proc_path.parent),
            })

    return vehicles
