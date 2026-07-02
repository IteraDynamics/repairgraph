"""
FastAPI router for the Review Repair product experience.

GET /internal/review              — self-contained HTML page
GET /internal/review/payload      — ReviewPayload as JSON
GET /internal/review/plan         — OperationalPlan as JSON
GET /internal/review/narrative    — OperationalNarrative as JSON
GET /internal/review/package      — CollisionWorkPackage as JSON
GET /internal/review/root-causes  — RootCauseAnalysis as JSON
GET /internal/review/vehicles     — available vehicles + active vehicle

Vehicle selection (applies to all review endpoints except /vehicles):
  All endpoints accept optional query parameters:
    ?oem=Hyundai&year=2025&model=Elantra&operation=quarter_panel_replacement

  Resolution order:
    1. Explicit query params (oem + year + model must all be provided)
    2. Active vehicle from data/active_vehicle.json (set by intake pipeline)
    3. Honda 2025 Accord demo fixture (hardcoded fallback)

  The active vehicle is set automatically when a packet is uploaded through
  /internal/intake/classify or /internal/intake/report and the readiness is
  'ready' or 'partial'. To reset to the demo, DELETE data/active_vehicle.json.

All outputs are advisory.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
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


# ---------------------------------------------------------------------------
# Vehicle context resolution
# ---------------------------------------------------------------------------

def _resolve_vehicle(
    oem: str | None,
    year: int | None,
    model: str | None,
    operation: str | None,
) -> tuple[str, int, str, str] | None:
    """Return (oem, year, model, operation) from params or active vehicle, else None.

    Returns None to signal: fall back to the Honda Accord demo fixture.
    """
    # 1. Explicit query params — all three identity fields required
    if oem and year and model:
        return (oem, year, model, operation or "quarter_panel_replacement")

    # 2. Active vehicle from disk (set by intake pipeline)
    try:
        from repairgraph.core.vehicle_store import get_active_vehicle
        ctx = get_active_vehicle()
        if ctx:
            return (ctx.oem, ctx.year, ctx.model, ctx.operation)
    except Exception:
        pass

    return None


def _build_model_for_vehicle(oem: str, year: int, model: str, operation: str):
    """Compile an OperationalModel from a normalized vehicle in data/normalized/.

    Uses initialize_repair_state (no demo events — real intake data represents
    an unstarted repair). Returns None if the procedure is not found on disk.
    """
    from repairgraph.query.loader import load_procedure, load_vehicle_structure
    from repairgraph.state.initialize import initialize_repair_state
    from repairgraph.topology.builder import build_topology_graph

    procedure = load_procedure(oem, year, model)
    if procedure is None:
        return None

    structure = load_vehicle_structure(oem, year, model)
    state = initialize_repair_state(procedure, structure)
    topology = build_topology_graph(procedure, structure)
    adapter = CollisionDomainAdapter.from_repair_state(state)

    # Preserve explicitly provided operation label if it differs from what
    # from_repair_state inferred (session.operation comes from the procedure).
    if operation and operation != adapter.operation:
        adapter = CollisionDomainAdapter(
            oem=adapter.oem,
            year=adapter.year,
            model=adapter.model,
            operation=operation,
            repair_area=adapter.repair_area,
            vehicle_systems=adapter.vehicle_systems,
            structural_involvement=adapter.structural_involvement,
            calibration_required=adapter.calibration_required,
            corrosion_protection_required=adapter.corrosion_protection_required,
            material_classifications=adapter.material_classifications,
            active_zones=adapter.active_zones,
        )

    compiler = RepairGraphCompiler()
    return compiler.compile_from_state(
        state=state,
        topology=topology,
        adapter=adapter,
    )


def _build_demo_model():
    """Compile the Honda 2025 Accord demo model (hardcoded fallback)."""
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
    return RepairGraphCompiler().compile_demo(adapter=adapter)


def _build_model(
    oem: str | None = None,
    year: int | None = None,
    model: str | None = None,
    operation: str | None = None,
):
    """Build an OperationalModel, resolving vehicle from params → active → demo."""
    vehicle = _resolve_vehicle(oem, year, model, operation)
    if vehicle is not None:
        v_oem, v_year, v_model, v_op = vehicle
        result = _build_model_for_vehicle(v_oem, v_year, v_model, v_op)
        if result is not None:
            return result
        # Procedure not found on disk — fall through to demo

    return _build_demo_model()


# ---------------------------------------------------------------------------
# Review page
# ---------------------------------------------------------------------------

@router.get(
    "/review",
    summary="Review Repair — collision product front door",
    response_class=HTMLResponse,
)
def get_review(
    oem: str | None = Query(None, description="OEM name (e.g. Honda, Hyundai)"),
    year: int | None = Query(None, description="Model year (e.g. 2025)"),
    model: str | None = Query(None, description="Vehicle model (e.g. Accord, Elantra)"),
    operation: str | None = Query(None, description="Operation (e.g. quarter_panel_replacement)"),
) -> HTMLResponse:
    """Return the Review Repair page as self-contained HTML.

    Answers immediately:
      - Can this repair proceed?
      - What is blocking it?
      - What matters most?
      - What is missing?
      - What should happen next?
      - What evidence supports those conclusions?

    Vehicle is resolved from query params → active vehicle → Honda Accord demo.
    Consumes OperationalModel via RepairGraphCompiler. Vanilla HTML/CSS/JS only.
    No CDN. No external JS. No frameworks.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    rca = build_root_cause_analysis(operational_model)
    payload = build_review_payload(operational_model)
    plan = build_operational_plan(operational_model, rca=rca)
    narrative = build_narrative(plan)
    pkg = build_execution_package(plan, narrative, operational_model)
    work_pkg = project_collision_work_package(pkg, narrative)
    html = build_review_page_html(
        payload,
        narrative=narrative.to_dict(),
        work_package=work_pkg.to_dict(),
    )
    return HTMLResponse(content=html, status_code=200)


# ---------------------------------------------------------------------------
# Vehicle list
# ---------------------------------------------------------------------------

@router.get(
    "/review/vehicles",
    summary="Available vehicles and active vehicle context",
)
def get_vehicles() -> dict[str, Any]:
    """Return available normalized vehicles and the current active vehicle.

    'available_vehicles' lists all vehicles found in data/normalized/ —
    both pre-authored fixtures (source: 'fixture') and intake-derived
    vehicles (source: 'intake').

    'active_vehicle' is the vehicle that will be used by /review and its
    sub-endpoints when no explicit oem/year/model query params are given.
    It is set automatically when a packet is processed through /intake/classify.

    To reset to the demo, call DELETE /internal/review/vehicles/active or
    delete data/active_vehicle.json directly.
    """
    from repairgraph.core.vehicle_store import get_active_vehicle, list_available_vehicles

    active = get_active_vehicle()
    available = list_available_vehicles()

    return {
        "active_vehicle": active.to_dict() if active else None,
        "available_vehicles": available,
        "demo_vehicle": {
            "oem": "Honda",
            "year": 2025,
            "model": "Accord",
            "operation": "quarter_panel_replacement",
            "source": "fixture",
        },
        "resolution_order": [
            "1. Explicit query params (?oem=&year=&model=)",
            "2. Active vehicle (data/active_vehicle.json — set by /intake pipeline)",
            "3. Honda 2025 Accord demo fixture (hardcoded fallback)",
        ],
        "endpoint_advisory": _ADVISORY,
    }


@router.delete(
    "/review/vehicles/active",
    summary="Clear the active vehicle context (revert to demo)",
)
def delete_active_vehicle() -> dict[str, Any]:
    """Clear the active vehicle context, reverting all review endpoints to the
    Honda Accord demo fixture until the next intake upload sets a new context.
    """
    from repairgraph.core.vehicle_store import clear_active_vehicle
    clear_active_vehicle()
    return {"cleared": True, "fallback": "Honda 2025 Accord demo fixture"}


# ---------------------------------------------------------------------------
# Sub-endpoints (all accept vehicle query params)
# ---------------------------------------------------------------------------

@router.get(
    "/review/root-causes",
    summary="Root cause analysis as JSON",
)
def get_root_causes(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return a deterministic root cause analysis for the resolved vehicle model.

    All outputs are advisory.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    rca = build_root_cause_analysis(operational_model)
    return {
        **rca.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/plan",
    summary="Operational Plan as JSON",
)
def get_operational_plan(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return a deterministic OperationalPlan for the resolved vehicle model.

    All outputs are advisory.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    rca = build_root_cause_analysis(operational_model)
    plan = build_operational_plan(operational_model, rca=rca)
    return {
        **plan.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/package",
    summary="Collision Work Package as JSON",
)
def get_work_package(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return the Collision Work Package for the resolved vehicle model.

    All outputs are advisory.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    rca = build_root_cause_analysis(operational_model)
    plan = build_operational_plan(operational_model, rca=rca)
    narrative = build_narrative(plan)
    pkg = build_execution_package(plan, narrative, operational_model)
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
def get_narrative(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return the narrated OperationalPlan for the resolved vehicle model.

    All outputs are advisory.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    rca = build_root_cause_analysis(operational_model)
    plan = build_operational_plan(operational_model, rca=rca)
    narrative = build_narrative(plan)
    return {
        **narrative.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/payload",
    summary="Review Repair payload as JSON",
)
def get_review_payload(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return the ReviewPayload as JSON for the resolved vehicle model.

    Exposes the same deterministic projection used by the HTML page.
    Useful for integration testing and downstream tooling.
    """
    operational_model = _build_model(oem=oem, year=year, model=model, operation=operation)
    payload = build_review_payload(operational_model)
    return {
        **payload.to_dict(),
        "endpoint_advisory": _ADVISORY,
    }
