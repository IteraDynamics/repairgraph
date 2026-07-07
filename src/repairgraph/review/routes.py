"""
FastAPI router for the Review Repair product experience.

GET /internal/review              — self-contained HTML page
GET /internal/review/payload      — ReviewPayload as JSON
GET /internal/review/plan         — OperationalPlan as JSON
GET /internal/review/narrative    — OperationalNarrative as JSON
GET /internal/review/package      — CollisionWorkPackage as JSON
GET /internal/review/root-causes  — RootCauseAnalysis as JSON
GET /internal/review/vehicles     — available vehicles + active vehicle

State progression (see docs/STATE_PROGRESSION.md):
GET    /internal/review/progress         — current projected repair state
POST   /internal/review/progress/events  — record a progress event
DELETE /internal/review/progress         — reset (clear the session journal)
GET    /internal/review/progress/ui      — progress page with record controls

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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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


def _load_state_bundle(oem: str, year: int, model: str):
    """Load procedure + structure and build (initial_state, topology).

    Returns None if the procedure is not found on disk.
    """
    from repairgraph.query.loader import load_procedure, load_vehicle_structure
    from repairgraph.state.initialize import initialize_repair_state
    from repairgraph.topology.builder import build_topology_graph

    procedure = load_procedure(oem, year, model)
    if procedure is None:
        return None

    structure = load_vehicle_structure(oem, year, model)
    initial_state = initialize_repair_state(procedure, structure)
    topology = build_topology_graph(procedure, structure)
    return initial_state, topology, procedure


def _manifest_overrides_from_procedure(procedure: dict) -> dict[str, Any]:
    """Derive source-manifest fields from a normalized procedure's source block.

    Intake-derived procedures carry the readiness and file list recorded at
    classification time. Authored fixtures are complete seed packets ('ready').
    """
    src = procedure.get("source")
    if isinstance(src, dict) and src.get("intake_id"):
        filenames = src.get("files", []) or []
        return {
            "source_count": len(filenames),
            "filenames": filenames,
            "readiness": src.get("readiness", "partial"),
        }
    return {
        "source_count": 1,
        "filenames": ["repair_procedure_quarter_panel.json"],
        "readiness": "ready",
    }


def _build_model_for_vehicle(oem: str, year: int, model: str, operation: str):
    """Compile an OperationalModel from a normalized vehicle in data/normalized/.

    Builds the initial RepairState with initialize_repair_state, then replays
    any journaled progress events (data/sessions/) over it so the review
    reflects where the repair currently stands. With no journal, the state is
    the unstarted initial projection. Returns None if the procedure is not
    found on disk.
    """
    from repairgraph.state.journal import load_session_events
    from repairgraph.state.project import project_repair_state

    bundle = _load_state_bundle(oem, year, model)
    if bundle is None:
        return None
    initial_state, topology, procedure = bundle

    events = load_session_events(oem, year, model)
    if events:
        try:
            state = project_repair_state(initial_state, events)
        except ValueError:
            # Journal references targets that no longer exist (e.g. the
            # procedure was re-normalized). Fall back to the initial state
            # rather than failing the review.
            state = initial_state
            events = []
    else:
        state = initial_state

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
        initial_state=initial_state if events else None,
        events=events or None,
        manifest_overrides=_manifest_overrides_from_procedure(procedure),
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
# State progression — record and inspect repair progress
# ---------------------------------------------------------------------------

class ProgressEventRequest(BaseModel):
    """A single progress event to record against the resolved vehicle session.

    target_type is derived from event_type (each event type applies to exactly
    one target type), so callers only supply the event and its target ID.
    """
    event_type: str
    target_id: str
    actor: str = "review_ui"
    notes: str | None = None


def _resolve_vehicle_or_404(
    oem: str | None,
    year: int | None,
    model: str | None,
    operation: str | None,
) -> tuple[str, int, str, str]:
    vehicle = _resolve_vehicle(oem, year, model, operation)
    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No vehicle context. Progress tracking requires an explicit "
                "vehicle (?oem=&year=&model=) or an active vehicle set by the "
                "intake pipeline. The Honda Accord demo fallback is a scripted "
                "walkthrough and does not accept progress events."
            ),
        )
    return vehicle


def _load_bundle_or_404(oem: str, year: int, model: str):
    bundle = _load_state_bundle(oem, year, model)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail=f"No normalized procedure found for {oem} {year} {model}.",
        )
    return bundle


def _project_current(initial_state, events):
    from repairgraph.state.project import project_repair_state

    if not events:
        return initial_state
    try:
        return project_repair_state(initial_state, events)
    except ValueError:
        return initial_state


def _progress_summary(oem: str, year: int, model: str, state, event_count: int) -> dict[str, Any]:
    open_gates = [g for g in state.qa_gates if g.status == "open"]
    open_blockers = [b for b in state.blockers if b.status == "open"]

    return {
        "vehicle": {"oem": oem, "year": year, "model": model},
        "session": {
            "session_id": state.session.session_id,
            "status": state.session.status,
            "operation": state.session.operation,
        },
        "counts": {
            "events_recorded": event_count,
            "open_qa_gates": len(open_gates),
            "open_blockers": len(open_blockers),
            "pending_actions": sum(1 for a in state.actions if a.status == "pending"),
            "complete_actions": sum(1 for a in state.actions if a.status == "complete"),
        },
        "phases": [
            {"phase": p.phase, "name": p.name, "label": p.label, "status": p.status}
            for p in state.phases
        ],
        "actions": [
            {
                "action_id": a.action_id,
                "phase": a.phase,
                "action_type": a.action_type,
                "target": a.target,
                "status": a.status,
            }
            for a in state.actions
        ],
        "qa_gates": [
            {
                "gate_id": g.gate_id,
                "category": g.category,
                "priority": g.priority,
                "status": g.status,
                "check": g.check,
                "blocks_completion": g.blocks_completion,
            }
            for g in state.qa_gates
        ],
        "blockers": [
            {
                "blocker_id": b.blocker_id,
                "type": b.type,
                "severity": b.severity,
                "status": b.status,
                "reason": b.reason,
            }
            for b in state.blockers
        ],
        "next_recommended_actions": list(state.next_recommended_actions),
        "endpoint_advisory": _ADVISORY,
    }


@router.get(
    "/review/progress",
    summary="Current repair progress for the resolved vehicle",
)
def get_progress(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Return the current projected repair state for the resolved vehicle.

    The state is the initial projection (from the normalized procedure) with
    all journaled progress events replayed over it. With no recorded events,
    every phase is not_started, every action pending, every QA gate open.

    All outputs are advisory.
    """
    from repairgraph.state.journal import load_session_events

    v_oem, v_year, v_model, _ = _resolve_vehicle_or_404(oem, year, model, operation)
    initial_state, _topology, _procedure = _load_bundle_or_404(v_oem, v_year, v_model)
    events = load_session_events(v_oem, v_year, v_model)
    state = _project_current(initial_state, events)

    summary = _progress_summary(v_oem, v_year, v_model, state, len(events))
    summary["events"] = [
        {
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "event_type": e.event_type,
            "actor": e.actor,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "notes": e.notes,
        }
        for e in events
    ]
    return summary


@router.get(
    "/review/progress/ui",
    summary="Repair Progress page — record work as it happens",
    response_class=HTMLResponse,
)
def get_progress_ui(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> HTMLResponse:
    """Return the Repair Progress page as self-contained HTML.

    Lists the resolved vehicle's QA gates and work actions with controls to
    record progress events (gate passed/failed, action started/completed).
    Recording an event updates the session journal; the Repair Review page
    reflects the new state on next load.

    No CDN. No external JS. No frameworks. All outputs are advisory.
    """
    from repairgraph.review.progress_page import build_progress_page_html
    from repairgraph.state.journal import load_session_events

    v_oem, v_year, v_model, _ = _resolve_vehicle_or_404(oem, year, model, operation)
    initial_state, _topology, _procedure = _load_bundle_or_404(v_oem, v_year, v_model)
    events = load_session_events(v_oem, v_year, v_model)
    state = _project_current(initial_state, events)

    summary = _progress_summary(v_oem, v_year, v_model, state, len(events))
    if oem and year and model:
        summary["_qs"] = f"?oem={v_oem}&year={v_year}&model={v_model}"
    html = build_progress_page_html(summary)
    return HTMLResponse(content=html, status_code=200)


@router.post(
    "/review/progress/events",
    summary="Record a progress event (gate passed, action completed, ...)",
)
def post_progress_event(
    body: ProgressEventRequest,
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Record a progress event against the resolved vehicle session.

    Supported event types: action_started, action_completed, action_blocked,
    action_marked_not_applicable, qa_gate_passed, qa_gate_failed,
    qa_gate_marked_not_applicable, blocker_resolved, phase_started,
    phase_completed, session_started, session_completed, session_cancelled.

    When a blocking QA gate is passed (or marked not applicable), its derived
    blocker (blocker:<gate_id>) is resolved automatically in the same request,
    so clearing a gate immediately unblocks whatever it was holding.

    The event is validated against the current state before it is journaled —
    unknown targets and incompatible event/target combinations are rejected
    with 422 and nothing is written.

    Recording an event documents that a human performed or verified work.
    All resulting state remains advisory.
    """
    from repairgraph.state.events import (
        EVENT_TARGET_COMPATIBILITY,
        make_repair_event,
    )
    from repairgraph.state.journal import append_session_events, load_session_events
    from repairgraph.state.project import project_repair_state
    from repairgraph.state.replay import build_state_diff, summarize_state_diff

    v_oem, v_year, v_model, _ = _resolve_vehicle_or_404(oem, year, model, operation)
    initial_state, _topology, _procedure = _load_bundle_or_404(v_oem, v_year, v_model)
    existing = load_session_events(v_oem, v_year, v_model)
    current = _project_current(initial_state, existing)

    allowed_targets = EVENT_TARGET_COMPATIBILITY.get(body.event_type)
    if not allowed_targets:
        raise HTTPException(status_code=422, detail=f"Invalid event type: {body.event_type}")
    target_type = next(iter(allowed_targets))

    try:
        new_events = [
            make_repair_event(
                event_type=body.event_type,
                actor=body.actor,
                target_type=target_type,
                target_id=body.target_id,
                notes=body.notes,
            )
        ]

        # Companion event: passing (or waiving) a QA gate resolves the blocker
        # that was derived from it, so the gate clearance actually unblocks work.
        if body.event_type in {"qa_gate_passed", "qa_gate_marked_not_applicable"}:
            blocker_id = f"blocker:{body.target_id}"
            blocker = next(
                (b for b in current.blockers if b.blocker_id == blocker_id and b.status == "open"),
                None,
            )
            if blocker is not None:
                new_events.append(
                    make_repair_event(
                        event_type="blocker_resolved",
                        actor=body.actor,
                        target_type="blocker",
                        target_id=blocker_id,
                        notes=f"Auto-resolved: QA gate {body.target_id} cleared.",
                    )
                )

        # Validate the full sequence against the current state before persisting.
        updated = project_repair_state(current, new_events)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    append_session_events(v_oem, v_year, v_model, new_events)

    diff = build_state_diff(current, updated)
    return {
        "recorded": True,
        "vehicle": {"oem": v_oem, "year": v_year, "model": v_model},
        "applied_events": [
            {"event_id": e.event_id, "event_type": e.event_type, "target_id": e.target_id}
            for e in new_events
        ],
        "session_status": {
            "previous": current.session.status,
            "current": updated.session.status,
        },
        "changes": summarize_state_diff(diff),
        "open_qa_gates": sum(1 for g in updated.qa_gates if g.status == "open"),
        "open_blockers": sum(1 for b in updated.blockers if b.status == "open"),
        "next_recommended_actions": list(updated.next_recommended_actions),
        "endpoint_advisory": _ADVISORY,
    }


@router.delete(
    "/review/progress",
    summary="Reset repair progress (clear the session event journal)",
)
def delete_progress(
    oem: str | None = Query(None),
    year: int | None = Query(None),
    model: str | None = Query(None),
    operation: str | None = Query(None),
) -> dict[str, Any]:
    """Clear all recorded progress events for the resolved vehicle, returning
    the repair to its initial unstarted state.
    """
    from repairgraph.state.journal import clear_session_events

    v_oem, v_year, v_model, _ = _resolve_vehicle_or_404(oem, year, model, operation)
    cleared = clear_session_events(v_oem, v_year, v_model)
    return {
        "cleared": cleared,
        "vehicle": {"oem": v_oem, "year": v_year, "model": v_model},
        "note": "Repair state reset to initial projection (all gates open, all actions pending).",
    }


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
