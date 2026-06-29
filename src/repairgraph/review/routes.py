"""
FastAPI router for the Review Repair product experience.

GET /internal/review         — self-contained HTML page
GET /internal/review/payload — ReviewPayload as JSON

Both endpoints compile the OperationalModel from demo fixtures and
project it through the ReviewPayload builder. No external dependencies.
All outputs are advisory.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.review_page import build_review_page_html
from repairgraph.review.review_payload import build_review_payload
from repairgraph.review.root_cause import build_root_cause_analysis

router = APIRouter(prefix="/internal", tags=["review"])

_ADVISORY = (
    "Review Repair outputs are advisory workflow intelligence. "
    "They do not certify repair completion, OEM compliance, or repair quality. "
    "All outputs require verification by a qualified technician against OEM procedures."
)


def _build_model():
    """Compile an OperationalModel from the Honda Accord demo fixtures."""
    adapter = CollisionDomainAdapter(
        oem="Honda",
        year=2025,
        model="Accord",
        operation="quarter_panel_replacement",
        repair_area="left_rear",
        structural_involvement=True,
        calibration_required=True,
        corrosion_protection_required=True,
    )
    compiler = RepairGraphCompiler()
    return compiler.compile_demo(adapter=adapter)


@router.get(
    "/review",
    summary="Review Repair — collision product front door",
    response_class=HTMLResponse,
)
def get_review() -> HTMLResponse:
    """Return the Review Repair page as self-contained HTML.

    Answers immediately:
      - Can this repair proceed?
      - What is blocking it?
      - What matters most?
      - What is missing?
      - What should happen next?
      - What evidence supports those conclusions?

    Consumes OperationalModel via RepairGraphCompiler. Vanilla HTML/CSS/JS only.
    No CDN. No external JS. No frameworks.
    """
    model = _build_model()
    payload = build_review_payload(model)
    html = build_review_page_html(payload)
    return HTMLResponse(content=html, status_code=200)


@router.get(
    "/review/root-causes",
    summary="Root cause analysis as JSON",
)
def get_root_causes() -> dict[str, Any]:
    """Return a deterministic root cause analysis for the current demo model.

    Collapses many downstream symptoms into the minimum set of causal
    explanations with impact scoring and recommended resolutions.
    All outputs are advisory.
    """
    model = _build_model()
    rca = build_root_cause_analysis(model)
    return {
        **rca.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/payload",
    summary="Review Repair payload as JSON",
)
def get_review_payload() -> dict[str, Any]:
    """Return the ReviewPayload as JSON.

    Exposes the same deterministic projection used by the HTML page.
    Useful for integration testing and downstream tooling.
    """
    model = _build_model()
    payload = build_review_payload(model)
    return {
        **payload.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }
