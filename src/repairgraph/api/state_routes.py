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
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.export_json import ADVISORY_NOTE, export_state_to_dict
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.replay import build_state_diff, replay_repair_state, summarize_state_diff
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
    summarize_timeline,
)
from repairgraph.state.visualization_payload import build_workflow_visualization_payload

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


@router.get("/accord/timeline", summary="Workflow timeline for projected Accord repair state")
def get_accord_timeline() -> dict[str, Any]:
    """Return ordered event, phase, and action timelines for the Honda 2025 Accord projected state.

    All timeline data is derived from the deterministic demo event ledger.
    No files are written.
    """
    state = build_accord_projected_state()
    return {
        "schema_name": "repairgraph.repair_state.timeline",
        "advisory": True,
        "endpoint_advisory": _ENDPOINT_ADVISORY,
        "advisory_note": ADVISORY_NOTE,
        "event_timeline": build_event_timeline(state),
        "phase_timeline": build_phase_timeline(state),
        "action_timeline": build_action_timeline(state),
        "summary": summarize_timeline(state),
    }


@router.get("/accord/replay", summary="Event-by-event replay with state diffs for projected Accord state")
def get_accord_replay() -> dict[str, Any]:
    """Return ordered state snapshots and lightweight diffs for the Honda 2025 Accord demo events.

    Each snapshot includes the applied event, a lightweight state summary, and
    the diff relative to the previous step. Replay is deterministic and side-effect free.
    No files are written.
    """
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    snapshots = replay_repair_state(initial, events)

    ordered_snapshots = []
    prev_state = initial
    for i, (event, snap) in enumerate(zip(events, snapshots)):
        diff = build_state_diff(prev_state, snap)
        diff_summary = summarize_state_diff(diff)
        ordered_snapshots.append({
            "step": i + 1,
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "actor": event.actor,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "notes": event.notes,
            },
            "state_summary": {
                "session_status": snap.session.status,
                "active_phase_ids": [p.name for p in snap.phases if p.status == "in_progress"],
                "completed_phase_count": sum(1 for p in snap.phases if p.status == "complete"),
                "completed_action_count": sum(1 for a in snap.actions if a.status == "complete"),
                "open_blocker_count": sum(1 for b in snap.blockers if b.status == "open"),
                "open_qa_gate_count": sum(
                    1 for g in snap.qa_gates if g.status in {"open", "in_review"}
                ),
                "next_recommended_actions": list(snap.next_recommended_actions),
            },
            "diff": diff,
            "diff_summary": diff_summary,
        })
        prev_state = snap

    return {
        "schema_name": "repairgraph.repair_state.replay",
        "advisory": True,
        "endpoint_advisory": _ENDPOINT_ADVISORY,
        "advisory_note": ADVISORY_NOTE,
        "event_count": len(events),
        "snapshot_count": len(snapshots),
        "ordered_snapshots": ordered_snapshots,
    }


@router.get("/accord/visualization", summary="Workflow visualization payload for projected Accord state")
def get_accord_visualization() -> dict[str, Any]:
    """Return the combined workflow visualization payload for the Honda 2025 Accord.

    Includes timelines, Mermaid diagrams, replay metadata, active context,
    blockers, and next actions. This is an introspection/debug payload, not a UI payload.
    No files are written.
    """
    state = build_accord_projected_state()
    payload = build_workflow_visualization_payload(state)
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
