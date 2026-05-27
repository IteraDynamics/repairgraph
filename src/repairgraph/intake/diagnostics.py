"""
Intake diagnostics layer for RepairGraph OEM repair packet intake.

Validates packet completeness, identifies missing document roles, surfaces
low-confidence classifications, and produces structured diagnostic reports.

This module is the primary explainability surface for the intake pipeline.
RepairGraph uses it to communicate what was found, what is missing, what
confidence it has, and what cannot yet be normalized.

All outputs are advisory and require qualified human review.
"""
from __future__ import annotations

from typing import Any

from repairgraph.intake.schema import IntakeDiagnostic, IntakeManifest

ESSENTIAL_ROLES = frozenset({"repair_procedure"})
RECOMMENDED_ROLES = frozenset({"welding", "corrosion_protection", "materials", "precautions"})

ROLE_DESCRIPTIONS: dict[str, str] = {
    "repair_procedure": "Main removal, installation, and replacement procedure steps",
    "sectioning": "Panel sectioning guidelines, cut locations, and overlap specifications",
    "welding": "Welding method specifications, weld counts, wire types, and technique requirements",
    "corrosion_protection": "Anti-corrosion treatment, sealer application, and cavity wax requirements",
    "materials": "Panel material classifications (UHSS, HSS, aluminum) and handling restrictions",
    "dimensions": "Panel gap, clearance, and alignment dimension specifications",
    "calibration": "ADAS sensor and camera calibration requirements post-repair",
    "precautions": "Safety precautions, hazard warnings, and handling notes",
}


def validate_packet_completeness(manifest: IntakeManifest) -> list[IntakeDiagnostic]:
    """Validate packet completeness and return a list of diagnostics.

    Checks for essential and recommended document roles, unreadable files,
    OEM detection, format support, and low-confidence classifications.
    Does not mutate the manifest.
    """
    diagnostics: list[IntakeDiagnostic] = []
    found = set(manifest.detected_packet.detected_roles)

    if not manifest.files:
        diagnostics.append(IntakeDiagnostic(
            code="EMPTY_PACKET",
            severity="error",
            message="No files were provided for intake.",
        ))
        return diagnostics

    # Essential role checks
    for role in sorted(ESSENTIAL_ROLES):
        if role not in found:
            diagnostics.append(IntakeDiagnostic(
                code=f"MISSING_ESSENTIAL_{role.upper()}",
                severity="error",
                message=f"Essential document role not detected: {role!r}",
                detail=ROLE_DESCRIPTIONS.get(role),
            ))

    # Recommended role checks
    for role in sorted(RECOMMENDED_ROLES):
        if role not in found:
            diagnostics.append(IntakeDiagnostic(
                code=f"MISSING_RECOMMENDED_{role.upper()}",
                severity="warning",
                message=f"Recommended document role not detected: {role!r}",
                detail=ROLE_DESCRIPTIONS.get(role),
            ))

    # Unreadable files
    unreadable = [f for f in manifest.files if f.errors]
    if unreadable:
        diagnostics.append(IntakeDiagnostic(
            code="UNREADABLE_FILES",
            severity="error",
            message=(
                f"{len(unreadable)} file(s) could not be read: "
                + ", ".join(f.filename for f in unreadable)
            ),
        ))

    # Low-confidence classifications
    low_conf = [f for f in manifest.files if not f.errors and f.confidence < 0.30]
    if low_conf:
        diagnostics.append(IntakeDiagnostic(
            code="LOW_CONFIDENCE_CLASSIFICATIONS",
            severity="warning",
            message=(
                f"{len(low_conf)} file(s) classified with confidence below 30%: "
                + ", ".join(f.filename for f in low_conf)
            ),
        ))

    # Unknown-role files
    unknown_role = [f for f in manifest.files if not f.errors and f.document_role == "unknown"]
    if unknown_role:
        diagnostics.append(IntakeDiagnostic(
            code="UNKNOWN_ROLE_FILES",
            severity="warning",
            message=(
                f"{len(unknown_role)} file(s) could not be classified into a known document role: "
                + ", ".join(f.filename for f in unknown_role)
            ),
        ))

    # OEM not detected
    if not manifest.detected_packet.detected_oem:
        diagnostics.append(IntakeDiagnostic(
            code="OEM_NOT_DETECTED",
            severity="warning",
            message=(
                "OEM could not be detected from the supplied files. "
                "Normalization and validation will require manual OEM assignment."
            ),
        ))

    # Year not detected
    if not manifest.detected_packet.detected_year:
        diagnostics.append(IntakeDiagnostic(
            code="YEAR_NOT_DETECTED",
            severity="info",
            message=(
                "Model year could not be detected. "
                "Year detection is heuristic and may miss non-standard document formats."
            ),
        ))

    # OEM conflict across files
    oems = {f.detected_oem for f in manifest.files if f.detected_oem and not f.errors}
    if len(oems) > 1:
        diagnostics.append(IntakeDiagnostic(
            code="OEM_CONFLICT",
            severity="warning",
            message=(
                f"Multiple OEMs detected across files: {sorted(oems)}. "
                "This may indicate files from different repair manuals were mixed."
            ),
        ))

    # Unsupported formats
    from repairgraph.intake.schema import SUPPORTED_EXTENSIONS
    unsupported = [f for f in manifest.files if f.extension not in SUPPORTED_EXTENSIONS]
    if unsupported:
        diagnostics.append(IntakeDiagnostic(
            code="UNSUPPORTED_FORMATS",
            severity="warning",
            message=(
                f"{len(unsupported)} file(s) use unsupported formats: "
                + ", ".join(f"{f.filename} ({f.extension})" for f in unsupported)
            ),
        ))

    return diagnostics


def build_intake_diagnostics(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a structured diagnostics summary from an IntakeManifest.

    Combines manifest diagnostics with completeness validation diagnostics.
    Returns severity-grouped counts, lists, and an overall assessment.
    """
    completeness = validate_packet_completeness(manifest)
    all_diags = list(manifest.diagnostics) + completeness

    errors = [d for d in all_diags if d.severity == "error"]
    warnings = [d for d in all_diags if d.severity == "warning"]
    infos = [d for d in all_diags if d.severity == "info"]

    def _to_dict(d: IntakeDiagnostic) -> dict[str, Any]:
        return {
            "code": d.code,
            "severity": d.severity,
            "message": d.message,
            "file_id": d.file_id,
            "detail": d.detail,
        }

    found = set(manifest.detected_packet.detected_roles)
    return {
        "advisory": True,
        "readiness": manifest.readiness,
        "total_diagnostics": len(all_diags),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
        "errors": [_to_dict(d) for d in errors],
        "warnings": [_to_dict(d) for d in warnings],
        "infos": [_to_dict(d) for d in infos],
        "missing_essential_roles": sorted(r for r in manifest.missing_roles if r in ESSENTIAL_ROLES),
        "missing_recommended_roles": sorted(r for r in manifest.missing_roles if r in RECOMMENDED_ROLES),
        "found_roles": sorted(found),
    }


def build_missing_role_report(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a report of missing document roles with descriptions and guidance.

    Describes what roles were detected, what is missing, and why each missing
    role matters for repair normalization.

    Missing roles are computed from detected roles (not from the pre-stored
    manifest.missing_roles list), so the report is accurate even for
    hand-assembled or partially-initialised manifests.
    """
    found = set(manifest.detected_packet.detected_roles)
    all_expected = ESSENTIAL_ROLES | RECOMMENDED_ROLES
    # Derive missing from what was actually detected, plus any explicitly listed
    missing = (all_expected - found) | set(manifest.missing_roles)

    total_expected = len(ESSENTIAL_ROLES) + len(RECOMMENDED_ROLES)
    found_count = len(found - {"unknown"})

    return {
        "found_roles": sorted(found),
        "missing_roles": sorted(missing),
        "missing_essential": sorted(missing & ESSENTIAL_ROLES),
        "missing_recommended": sorted(missing & RECOMMENDED_ROLES),
        "role_descriptions": {
            role: ROLE_DESCRIPTIONS.get(role, "No description available.")
            for role in sorted(missing)
        },
        "coverage_note": (
            f"Detected {found_count} of {total_expected} expected roles. "
            f"{len(missing)} role(s) missing."
        ),
        "advisory": (
            "Missing roles indicate document categories RepairGraph could not identify. "
            "This may mean documents were not supplied, could not be read, or use "
            "non-standard formatting that heuristic classification did not recognize. "
            "RepairGraph does not infer or fabricate missing document content."
        ),
    }
