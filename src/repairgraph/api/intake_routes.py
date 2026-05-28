"""
Internal FastAPI router for RepairGraph OEM repair packet intake endpoints.

Accepts uploaded files, classifies intake packets using lightweight heuristics,
and returns intake manifests (JSON) or HTML reports. No files are retained
after the response — all processing is in-memory.

Local/internal demo use only. No authentication, no persistence, no DB.

Advisory: RepairGraph processes OEM repair information supplied by authorized
users. It is not an OEM document distribution platform. All outputs are
heuristic estimates requiring qualified human review.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from repairgraph.intake.classify import classify_intake_packet, summarize_intake_manifest
from repairgraph.intake.evidence import build_intake_evidence_payload
from repairgraph.intake.report import build_intake_html_report
from repairgraph.intake.schema import IntakeManifest
from repairgraph.intake.upload_page import build_intake_upload_page

router = APIRouter(prefix="/internal/intake", tags=["intake"])

_ENDPOINT_ADVISORY = (
    "This endpoint is local/internal demo use only. "
    "RepairGraph processes OEM repair information supplied by authorized users. "
    "It is not an OEM document distribution platform. "
    "No files are retained after the response. "
    "All outputs are advisory heuristic estimates requiring qualified review."
)


def _serialize_manifest(manifest: IntakeManifest) -> dict[str, Any]:
    """Serialize an IntakeManifest to a JSON-compatible dict."""
    return {
        "schema_name": "repairgraph.intake_manifest",
        "schema_version": "0.1",
        "advisory": manifest.advisory,
        "endpoint_advisory": _ENDPOINT_ADVISORY,
        "intake_id": manifest.intake_id,
        "created_at": manifest.created_at,
        "readiness": manifest.readiness,
        "detected_packet": {
            "detected_oem": manifest.detected_packet.detected_oem,
            "detected_model": manifest.detected_packet.detected_model,
            "detected_year": manifest.detected_packet.detected_year,
            "detected_operation": manifest.detected_packet.detected_operation,
            "oem_confidence": manifest.detected_packet.oem_confidence,
            "detected_roles": manifest.detected_packet.detected_roles,
            "file_count": manifest.detected_packet.file_count,
        },
        "files": [
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "extension": f.extension,
                "size_bytes": f.size_bytes,
                "detected_oem": f.detected_oem,
                "detected_model": f.detected_model,
                "detected_year": f.detected_year,
                "detected_operation": f.detected_operation,
                "document_role": f.document_role,
                "supporting_roles": f.supporting_roles,
                "role_scores": f.role_scores,
                "role_evidence": f.role_evidence,
                "confidence": f.confidence,
                "warnings": f.warnings,
                "errors": f.errors,
            }
            for f in manifest.files
        ],
        "missing_roles": manifest.missing_roles,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "file_id": d.file_id,
                "detail": d.detail,
            }
            for d in manifest.diagnostics
        ],
        "summary": summarize_intake_manifest(manifest),
    }


async def _process_uploads(files: list[UploadFile]) -> IntakeManifest:
    """Write uploaded files to a temp dir, classify the packet, return manifest.

    Temp directory and all files are deleted when this function returns.
    """
    if not files:
        raise HTTPException(status_code=422, detail="No files provided for intake.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_paths: list[Path] = []
        for upload in files:
            name = Path(upload.filename or "upload.bin").name
            tmp_path = Path(tmpdir) / name
            content = await upload.read()
            tmp_path.write_bytes(content)
            tmp_paths.append(tmp_path)
        return classify_intake_packet(tmp_paths)


@router.get(
    "",
    summary="OEM repair packet intake upload page",
    response_class=HTMLResponse,
)
async def get_intake_page() -> HTMLResponse:
    """Return the self-contained HTML upload page for OEM repair packet intake.

    The page includes a file picker, drag-and-drop zone, and results area.
    It uses fetch() to call POST /internal/intake/classify and /report.
    No files are retained. Local/internal use only.
    """
    return HTMLResponse(content=build_intake_upload_page(), status_code=200)


@router.post("/classify", summary="Classify an OEM repair packet")
async def post_intake_classify(
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    """Accept uploaded files and return a JSON intake manifest.

    Classifies each file's document role and detects OEM/vehicle metadata
    using lightweight heuristics. No files are retained. All outputs are
    advisory heuristic estimates.
    """
    manifest = await _process_uploads(files)
    return _serialize_manifest(manifest)


@router.post(
    "/report",
    summary="Generate an HTML intake report for an OEM repair packet",
    response_class=HTMLResponse,
)
async def post_intake_report(
    files: list[UploadFile] = File(default=[]),
) -> HTMLResponse:
    """Accept uploaded files and return a self-contained HTML intake report.

    Classifies each file and generates a portable HTML report with diagnostics,
    role coverage, confidence indicators, readiness assessment, and an Evidence
    Inspector section with per-file classification explanations.
    No files are retained.
    """
    manifest = await _process_uploads(files)
    html_content = build_intake_html_report(manifest)
    return HTMLResponse(content=html_content, status_code=200)


@router.post("/evidence", summary="Return intake evidence inspector payload as JSON")
async def post_intake_evidence(
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    """Accept uploaded files and return a structured evidence/debug payload.

    Classifies the packet and builds a per-file evidence payload that explains
    why each file was classified, what evidence drove decisions, text quality,
    breadcrumb navigation found, role scores, and confidence reasoning.

    No files are retained. All outputs are advisory heuristic estimates.
    """
    manifest = await _process_uploads(files)
    return build_intake_evidence_payload(manifest)
