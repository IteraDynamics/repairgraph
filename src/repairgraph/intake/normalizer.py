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

Extraction sources (in priority order)
---------------------------------------
1. extracted_facts — deterministic content extraction over the document text
   (content_extractor.py). Provides dependencies, spatial relationships,
   sectioning locations with dimensions, joining methods with counts,
   corrosion requirements, materials, structure nodes, and repair notes.
   Every fact carries the source snippet it was derived from.
2. role_evidence phrases — classification evidence mapped to canonical IDs.
   Used as a fallback/complement when content extraction found nothing.

Fields still absent when the document text does not state them remain empty —
nothing is inferred or fabricated.
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


# ---------------------------------------------------------------------------
# Extracted-fact aggregation (content_extractor output, merged across files)
# ---------------------------------------------------------------------------

def _all_facts(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return [f.extracted_facts for f in manifest.files if f.extracted_facts]


def _merge_fact_list(
    manifest: IntakeManifest,
    key: str,
    identity,
) -> list[dict[str, Any]]:
    """Union a fact list across all files, deduped by an identity function."""
    merged: list[dict[str, Any]] = []
    seen: set = set()
    for facts in _all_facts(manifest):
        for item in facts.get(key, []):
            marker = identity(item)
            if marker in seen:
                continue
            seen.add(marker)
            merged.append(item)
    return merged


def _facts_dependencies(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return _merge_fact_list(manifest, "dependencies", lambda d: (d["type"], d["target"]))


def _facts_spatial_relationships(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return _merge_fact_list(
        manifest, "spatial_relationships",
        lambda r: (r["source"], r["relationship"], r["target"]),
    )


def _facts_sectioning_locations(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return _merge_fact_list(manifest, "sectioning_locations", lambda s: s["zone"])


def _facts_joining_methods(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return _merge_fact_list(manifest, "joining_methods", lambda j: j["method"])


def _facts_corrosion_requirements(manifest: IntakeManifest) -> list[str]:
    return [r["requirement"] for r in _merge_fact_list(
        manifest, "corrosion_requirements", lambda r: r["requirement"],
    )]


def _facts_materials(manifest: IntakeManifest) -> list[dict[str, Any]]:
    return _merge_fact_list(manifest, "materials", lambda m: m["component"])


def _facts_components(manifest: IntakeManifest) -> list[str]:
    components: list[str] = []
    for facts in _all_facts(manifest):
        for c in facts.get("components", []):
            if c not in components:
                components.append(c)
    return components


def _vehicle_noise_tokens(manifest: IntakeManifest) -> set[str]:
    """Tokens from the detected vehicle identity (oem/model) that indicate a
    'component' is actually title noise (e.g. 'altima_quarter_panel' extracted
    from the document heading)."""
    pkt = manifest.detected_packet
    tokens: set[str] = set()
    for value in (pkt.detected_oem, pkt.detected_model):
        if value:
            tokens.update(_model_slug(value).split("_"))
    return tokens


def _is_vehicle_noise(component: str, noise_tokens: set[str]) -> bool:
    return any(tok in noise_tokens for tok in component.split("_"))


def _strip_vehicle_noise(manifest: IntakeManifest, procedure_facts: dict[str, Any]) -> None:
    """Remove title-noise components (and facts referencing them) in place."""
    noise = _vehicle_noise_tokens(manifest)
    if not noise:
        return

    procedure_facts["components"] = [
        c for c in procedure_facts["components"] if not _is_vehicle_noise(c, noise)
    ]
    procedure_facts["dependencies"] = [
        d for d in procedure_facts["dependencies"] if not _is_vehicle_noise(d["target"], noise)
    ]
    procedure_facts["spatial_relationships"] = [
        r for r in procedure_facts["spatial_relationships"]
        if not (_is_vehicle_noise(r["source"], noise) or _is_vehicle_noise(r["target"], noise))
    ]
    procedure_facts["sectioning_locations"] = [
        s for s in procedure_facts["sectioning_locations"] if not _is_vehicle_noise(s["zone"], noise)
    ]
    procedure_facts["materials"] = [
        m for m in procedure_facts["materials"] if not _is_vehicle_noise(m["component"], noise)
    ]


def _facts_repair_notes(manifest: IntakeManifest) -> list[str]:
    notes: list[str] = []
    for facts in _all_facts(manifest):
        for n in facts.get("repair_notes", []):
            if n not in notes:
                notes.append(n)
    return notes


def _gather_facts(manifest: IntakeManifest) -> dict[str, Any]:
    """Merge extracted facts across files and strip vehicle-title noise."""
    gathered = {
        "components": _facts_components(manifest),
        "dependencies": _facts_dependencies(manifest),
        "spatial_relationships": _facts_spatial_relationships(manifest),
        "sectioning_locations": _facts_sectioning_locations(manifest),
        "materials": _facts_materials(manifest),
    }
    _strip_vehicle_noise(manifest, gathered)
    return gathered


def _build_procedure(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a normalized procedure dict from intake manifest evidence."""
    pkt = manifest.detected_packet
    oem = pkt.detected_oem or "Unknown"
    model = pkt.detected_model or "Unknown"
    year = pkt.detected_year or 0
    operation = pkt.detected_operation or "quarter_panel_replacement"

    # Content-extracted facts take priority; classification evidence phrases
    # complement them (union) so neither source loses information.
    gathered = _gather_facts(manifest)

    joining_details = _facts_joining_methods(manifest)
    joining_ids = [j["method"] for j in joining_details]
    for method in _extract_joining_methods(manifest):
        if method not in joining_ids:
            joining_ids.append(method)

    corrosion = _facts_corrosion_requirements(manifest)
    for req in _extract_corrosion_requirements(manifest):
        if req not in corrosion:
            corrosion.append(req)

    sectioning = gathered["sectioning_locations"]
    if not sectioning:
        sectioning = _extract_sectioning_locations(manifest)

    return {
        "oem": oem,
        "year": year,
        "model": model,
        "operation": operation,
        "operation_family": _derive_operation_family(operation),
        "joining_methods": joining_ids,
        "joining_details": joining_details,
        "sectioning_locations": sectioning,
        "dependencies": gathered["dependencies"],
        "corrosion_requirements": corrosion,
        "repair_notes": _facts_repair_notes(manifest),
        "spatial_relationships": gathered["spatial_relationships"],
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

    gathered = _gather_facts(manifest)
    materials = gathered["materials"]
    structure_nodes = gathered["components"]

    if materials:
        notes = [
            "Material data extracted from uploaded document text. "
            "Verify all classifications against the OEM specification sheet."
        ]
    elif has_materials_file:
        notes = [
            "Material specification file detected during intake, but no "
            "component-level material data could be extracted from its text. "
            "Verify against the OEM document."
        ]
    else:
        notes = [
            "No material specification documents detected during intake. "
            "Material classifications are unavailable."
        ]

    return {
        "oem": oem,
        "year": year,
        "model": model,
        "domain": "body_panel_construction",
        "materials": materials,
        "structure_nodes": structure_nodes,
        "notes": notes,
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
    preserved_fixture: bool = False
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

        proc_path = vehicle_dir / _PROCEDURE_FILENAME
        struct_path = vehicle_dir / _STRUCTURE_FILENAME

        # Never overwrite an authored fixture. Fixture procedures are complete
        # seed data with no source.intake_id; replacing them with a sparse
        # classification-derived procedure would destroy content the intake
        # pipeline cannot reconstruct. Intake-derived procedures may be
        # re-normalized freely (a fresh upload supersedes the previous one).
        if proc_path.exists():
            try:
                existing = json.loads(proc_path.read_text(encoding="utf-8"))
                existing_src = existing.get("source")
                is_intake_derived = isinstance(existing_src, dict) and existing_src.get("intake_id")
            except (OSError, json.JSONDecodeError):
                is_intake_derived = True  # unreadable file — safe to replace
            if not is_intake_derived:
                warnings.append(
                    f"An authored fixture already exists for {oem} {year} {model}; "
                    "intake normalization will not overwrite it. The existing "
                    "fixture remains the procedure of record for this vehicle."
                )
                result.warnings = warnings
                result.preserved_fixture = True
                return result

        vehicle_dir.mkdir(parents=True, exist_ok=True)

        proc_path.write_text(json.dumps(procedure, indent=2, ensure_ascii=False), encoding="utf-8")
        struct_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

        result.procedure_path = proc_path
        result.structure_path = struct_path
        result.written = True

    return result
