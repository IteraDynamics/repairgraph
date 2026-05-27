"""
Internal FastAPI router for RepairGraph state workflow and AR payload endpoints.

All endpoints are demo/internal only. They produce deterministic advisory
workflow intelligence from the Honda 2025 Accord seed dataset. No files are
written, no data is persisted, and no authentication is required.

Advisory: All outputs require OEM procedure verification and qualified
technician review before acting on any recommendation.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from repairgraph.state.blockers import summarize_blockers
from repairgraph.state.demo import (
    build_accord_ar_payload,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.export_json import ADVISORY_NOTE, export_state_to_dict
from repairgraph.state.next_actions import summarize_next_actions

router = APIRouter(prefix="/internal/state", tags=["state"])

_ENDPOINT_ADVISORY = (
    "This endpoint returns advisory workflow intelligence. "
    "It is a local/internal demo endpoint and is not an authenticated "
    "production API surface. No repair certification or OEM compliance "
    "is implied."
)


@router.get("/accord/initial", summary="Initial Accord repair state")
def get_accord_initial() -> dict[str, Any]:
    """Return the initial (un-projected) RepairState for the Honda 2025 Accord.

    Loads the Accord procedure, initializes state via initialize_repair_state(),
    and serializes with export_state_to_dict(). No events are applied.
    """
    state = build_accord_initial_state()
    payload = export_state_to_dict(state)
    payload["endpoint_advisory"] = _ENDPOINT_ADVISORY
    return payload


@router.get("/accord/projected", summary="Projected Accord repair state after demo events")
def get_accord_projected() -> dict[str, Any]:
    """Return the RepairState for the Honda 2025 Accord after the deterministic demo event ledger.

    Applies the same event sequence used by the state CLI. No files are written.
    """
    state = build_accord_projected_state()
    payload = export_state_to_dict(state)
    payload["endpoint_advisory"] = _ENDPOINT_ADVISORY
    return payload


@router.get("/accord/ar-payload", summary="AR workflow payload for projected Accord state")
def get_accord_ar_payload() -> dict[str, Any]:
    """Return the AR workflow payload for the Honda 2025 Accord projected state.

    Builds the same deterministic projected state and passes it through
    build_ar_workflow_payload(). No files are written.
    """
    payload = build_accord_ar_payload()
    payload["endpoint_advisory"] = _ENDPOINT_ADVISORY
    return payload


@router.get("/accord/summary", summary="Compact summary of projected Accord repair state")
def get_accord_summary() -> dict[str, Any]:
    """Return a compact summary of the projected Accord state.

    Includes session, workflow counts, open blockers, and next actions.
    """
    state = build_accord_projected_state()
    return {
        "schema_name": "repairgraph.repair_state.summary",
        "advisory": True,
        "endpoint_advisory": _ENDPOINT_ADVISORY,
        "session": {
            "session_id": state.session.session_id,
            "oem": state.session.oem,
            "year": state.session.year,
            "model": state.session.model,
            "status": state.session.status,
            "current_phase": state.session.current_phase,
        },
        "workflow_summary": {
            "phase_count": len(state.phases),
            "action_count": len(state.actions),
            "qa_gate_count": len(state.qa_gates),
            "blocker_count": len(state.blockers),
            "event_count": len(state.events),
            "next_action_count": len(state.next_recommended_actions),
        },
        "open_blockers": summarize_blockers(state),
        "next_actions": summarize_next_actions(state),
        "advisory_note": ADVISORY_NOTE,
    }
