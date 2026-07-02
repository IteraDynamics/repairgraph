"""
Intake normalization layer.

Converts a classified IntakeManifest into normalized procedure JSON files and
writes them to data/normalized/<oem>/<year>_<model>/. This is the bridge
between the intake classification pipeline and the RepairGraph compiler.

Design principles
-----------------
- Only records what the intake manifest actually contains — never fabricates.
- Evidence phrases captured by the classifier are mapped to canonical IDs.
- Fields that cannot be derived (spatial_relationships, component dependencies,
  OEM measurements) are left empty; the compiler handles sparse procedures.
- All output is marked intake-derived and advisory.
- Writes are atomic per vehicle: procedure + structure both succeed or neither.

What we CAN extract from role_evidence
---------------------------------------
- joining_methods   → from welding-role file evidence phrases
- corrosion_requirements → from corrosion_protection-role file evidence phrases
- sectioning_locations   → presence of sectioning-role file signals partial data
- operation, oem, model, year, operation_family → from IntakePacket detection

What we CANNOT extract (left empty)
-------------------------------------
- spatial_relationships   (requires geometric/spatial parsing)
- dependencies            (requires procedure logic parsing)
- repair_notes            (requires full text extraction)
- vehicle_structure.json materials (requires spec-sheet data)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repairgraph.intake.schema import IntakeManifest

# ---------------------------------------------------------------------------
# Evidence-to-canonical-ID mappings
# These map the fixed role_evidence phrases from classify.py to the
# normalized field values consumed by the RepairGraph compiler.
# ---------------------------------------------------------------------------

_EVIDENCE_TO_JOINING_METHOD: dict[str, str] = {
    "spot weld": "spot_weld",
    "weld points": "spot_weld",
    "resistance spot welding": "resistance_spot_weld",
    "plug weld": "plug_weld",
    "mig welding": "mig_welding",
    "mag welding": "mag_welding",
    "mig brazing": "mig_brazing",
    "adhesive bonding": "adhesive_bonding",
    "adhesive bond": "adhesive_bonding",
    "hemming": "hemming",
    "rivet": "structural_rivet",
    "brazing": "brazing",
}

_EVIDENCE_TO_CORROSION_REQ: dict[str, str] = {
    "seam sealer": "sealer_application_required",
    "body sealant": "sealer_application_required",
    "adhesive application": "adhesive_application_required",
    "cavity wax": "undercoating_application_required",
    "underbody": "undercoating_application_required",
    "undercoat": "undercoating_application_required",
    "electrocoat": "undercoating_application_required",
    "anti-corrosion": "corrosion_protection_required",
    "rust preventative": "corrosion_protection_required",
    "corrosion protection": "corrosion_protection_required",
}

# If any corrosion-role file is present, we know sealer is required at minimum.
_CORROSION_ROLE_DEFAULT = "sealer_application_required"

_OPERATION_FAMILY_MAP: dict[str, str] = {
    "quarter_panel_replacement": "quarter_panel",
    "rear_panel_replacement": "quarter_panel",
    "outer_panel_replacement": "quarter_panel",
    "bed_side_panel_replacement": "quarter_panel",
    "roof_panel_replacement": "roof_panel",
    "rocker_panel_replacement": "rocker_panel",
    "pillar_replacement": "pillar",
    "door_skin_replacement": "door",
    "hood_replacement": "hood",
}

_NORMALIZED_DIR = Path("data/normalized")
_PROCEDURE_FILENAME = "repair_procedure_quarter_panel.json"
_STRUCTURE_FILENAME = "vehicle_structure.json"

_ADVISORY = (
    "This procedure file was derived from intake classification heuristics, "
    "not from direct OEM document parsing. Joining methods, corrosion requirements, "
    "and other fields reflect evidence detected during classification and may be "
    "incomplete. All outputs require verification by a qualified technician against "
    "the applicable OEM procedures before operational use."
)


def _model_slug(model: str) -> str:
    return model.lower().replace("-", "_").replace(" ", "_")


def _oem_slug(oem: str) -> str:
    return oem.lower().replace(" ", "_")


def _extract_joining_methods(manifest: IntakeManifest) -> list[str]:
    """Extract joining method IDs from welding and repair_procedure file evidence."""
    found: list[str] = []
    seen: set[str] = set()
    # Search all files (welding evidence can appear in repair_procedure files too)
    for f in manifest.files:
        if f.document_role not in ("welding", "repair_procedure", "materials"):
            continue
        for phrase in f.role_evidence:
            method = _EVIDENCE_TO_JOINING_METHOD.get(phrase.lower())
            if method and method not in seen:
                seen.add(method)
                found.append(method)
    return found


def _extract_corrosion_requirements(manifest: IntakeManifest) -> list[str]:
    """Extract corrosion requirement IDs from corrosion_protection file evidence."""
    found: list[str] = []
    seen: set[str] = set()
    has_corrosion_role = any(f.document_role == "corrosion_protection" for f in manifest.files)

    for f in manifest.files:
        if f.document_role not in ("corrosion_protection", "repair_procedure"):
            continue
        for phrase in f.role_evidence:
            req = _EVIDENCE_TO_CORROSION_REQ.get(phrase.lower())
            if req and req not in seen:
                seen.add(req)
                found.append(req)

    if has_corrosion_role and not found:
        found.append(_CORROSION_ROLE_DEFAULT)

    return found


def _extract_sectioning_locations(manifest: IntakeManifest) -> list[dict]:
    """Return generic sectioning location stubs if sectioning documents detected."""
    has_sectioning = any(f.document_role == "sectioning" for f in manifest.files)
    if not has_sectioning:
        return []
    # We know sectioning documents exist but cannot derive zone names without
    # full text extraction. Return a single advisory stub.
    return [
        {
            "zone": "intake_detected_section",
            "description": (
                "Sectioning document detected during intake. "
                "Verify exact cut locations against OEM procedure."
            ),
        }
    ]


def _derive_operation_family(operation: str | None) -> str:
    if not operation:
        return "quarter_panel"
    return _OPERATION_FAMILY_MAP.get(operation, "body_panel")


def _build_procedure(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a normalized procedure dict from intake manifest evidence."""
    pkt = manifest.detected_packet
    oem = pkt.detected_oem or "Unknown"
    model = pkt.detected_model or "Unknown"
    year = pkt.detected_year or 0
    operation = pkt.detected_operation or "quarter_panel_replacement"

    return {
        "oem": oem,
        "year": year,
        "model": model,
        "operation": operation,
        "operation_family": _derive_operation_family(operation),
        "joining_methods": _extract_joining_methods(manifest),
        "sectioning_locations": _extract_sectioning_locations(manifest),
        "dependencies": [],
        "corrosion_requirements": _extract_corrosion_requirements(manifest),
        "repair_notes": [],
        "spatial_relationships": [],
        "source": {
            "intake_id": manifest.intake_id,
            "detected_roles": pkt.detected_roles,
            "files": [f.filename for f in manifest.files],
            "readiness": manifest.readiness,
            "advisory": _ADVISORY,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _build_structure(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a normalized vehicle structure dict from intake manifest evidence."""
    pkt = manifest.detected_packet
    oem = pkt.detected_oem or "Unknown"
    model = pkt.detected_model or "Unknown"
    year = pkt.detected_year or 0

    has_materials_file = any(f.document_role == "materials" for f in manifest.files)

    return {
        "oem": oem,
        "year": year,
        "model": model,
        "domain": "body_panel_construction",
        # Material details require spec-sheet parsing; cannot be inferred from
        # classification evidence alone.
        "materials": [],
        "structure_nodes": [],
        "notes": (
            [
                "Material specification file detected during intake. "
                "Component-level material classifications require OEM document "
                "review and cannot be automatically derived from classification evidence."
            ]
            if has_materials_file
            else [
                "No material specification documents detected during intake. "
                "Material classifications are unavailable."
            ]
        ),
        "source": {
            "intake_id": manifest.intake_id,
            "advisory": _ADVISORY,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# NormalizationResult
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    """Result of normalizing an IntakeManifest."""
    oem: str
    year: int
    model: str
    operation: str
    intake_id: str
    readiness: str
    procedure: dict[str, Any]
    structure: dict[str, Any]
    procedure_path: Path | None = None
    structure_path: None | Path = None
    written: bool = False
    warnings: list[str] = field(default_factory=list)
    advisory: str = _ADVISORY

    @property
    def vehicle_label(self) -> str:
        return f"{self.year} {self.oem} {self.model}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "oem": self.oem,
            "year": self.year,
            "model": self.model,
            "operation": self.operation,
            "intake_id": self.intake_id,
            "readiness": self.readiness,
            "written": self.written,
            "procedure_path": str(self.procedure_path) if self.procedure_path else None,
            "structure_path": str(self.structure_path) if self.structure_path else None,
            "warnings": self.warnings,
            "advisory": self.advisory,
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def normalize_intake_manifest(
    manifest: IntakeManifest,
    output_dir: Path | None = None,
    write: bool = True,
) -> NormalizationResult:
    """Convert a classified IntakeManifest into normalized procedure JSON files.

    Extracts joining methods, corrosion requirements, and vehicle metadata from
    the manifest's role_evidence fields and writes them to the normalized data
    directory so the RepairGraph compiler can load and compile them.

    Args:
        manifest:   The IntakeManifest from classify_intake_packet().
        output_dir: Override output directory (default: data/normalized/).
        write:      If False, build result without writing to disk (for testing).

    Returns:
        NormalizationResult with procedure/structure dicts and file paths.
    """
    pkt = manifest.detected_packet
    oem = pkt.detected_oem or ""
    model = pkt.detected_model or ""
    year = pkt.detected_year or 0
    operation = pkt.detected_operation or "quarter_panel_replacement"

    warnings: list[str] = []

    if not oem:
        warnings.append("OEM could not be detected — normalization may produce incorrect paths.")
    if not model:
        warnings.append("Vehicle model could not be detected.")
    if not year:
        warnings.append("Vehicle year could not be detected.")

    procedure = _build_procedure(manifest)
    structure = _build_structure(manifest)

    result = NormalizationResult(
        oem=oem or "Unknown",
        year=year,
        model=model or "Unknown",
        operation=operation,
        intake_id=manifest.intake_id,
        readiness=manifest.readiness,
        procedure=procedure,
        structure=structure,
        warnings=warnings,
    )

    if write and oem and model and year:
        base = output_dir or _NORMALIZED_DIR
        vehicle_dir = base / _oem_slug(oem) / f"{year}_{_model_slug(model)}"
        vehicle_dir.mkdir(parents=True, exist_ok=True)

        proc_path = vehicle_dir / _PROCEDURE_FILENAME
        struct_path = vehicle_dir / _STRUCTURE_FILENAME

        proc_path.write_text(json.dumps(procedure, indent=2, ensure_ascii=False), encoding="utf-8")
        struct_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

        result.procedure_path = proc_path
        result.structure_path = struct_path
        result.written = True

    return result
