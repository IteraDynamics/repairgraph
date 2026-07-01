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
from repairgraph.core.execution_package import build_execution_package, project_collision_work_package
from repairgraph.review.narrator import build_narrative
from repairgraph.review.operational_planner import build_operational_plan
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
    rca = build_root_cause_analysis(model)
    payload = build_review_payload(model)
    plan = build_operational_plan(model, rca=rca)
    narrative = build_narrative(plan)
    pkg = build_execution_package(plan, narrative, model)
    work_pkg = project_collision_work_package(pkg, narrative)
    html = build_review_page_html(
        payload,
        narrative=narrative.to_dict(),
        work_package=work_pkg.to_dict(),
    )
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
    "/review/plan",
    summary="Operational Plan as JSON",
)
def get_operational_plan() -> dict[str, Any]:
    """Return a deterministic OperationalPlan for the current demo model.

    The plan answers: what is the highest-leverage action the shop should
    take next, why that action, and what it unlocks. All outputs are advisory.
    """
    model = _build_model()
    rca = build_root_cause_analysis(model)
    plan = build_operational_plan(model, rca=rca)
    return {
        **plan.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/package",
    summary="Collision Work Package as JSON",
)
def get_work_package() -> dict[str, Any]:
    """Return the current Collision Work Package for the demo model.

    The work package converts the next highest-leverage task into a
    structured, executable unit of work with prerequisites, required
    verifications, execution steps, and completion criteria.
    All outputs are advisory.
    """
    model = _build_model()
    rca = build_root_cause_analysis(model)
    plan = build_operational_plan(model, rca=rca)
    narrative = build_narrative(plan)
    pkg = build_execution_package(plan, narrative, model)
    work_pkg = project_collision_work_package(pkg, narrative)
    return {
        **work_pkg.to_dict(),
        "execution_package": pkg.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/narrative",
    summary="Operational Narrative as JSON",
)
def get_narrative() -> dict[str, Any]:
    """Return the narrated OperationalPlan for the current demo model.

    The narrative translates deterministic planner output into natural
    operational language suitable for technicians, managers, and executives.
    All outputs are advisory.
    """
    model = _build_model()
    rca = build_root_cause_analysis(model)
    plan = build_operational_plan(model, rca=rca)
    narrative = build_narrative(plan)
    return {
        **narrative.to_dict(),
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
