"""
Shared deterministic demo builder for Honda 2025 Accord repair state and AR payload.

Used by CLI tools and internal API endpoints to produce consistent, repeatable demo
outputs without writing files or requiring external dependencies.

All outputs are advisory workflow intelligence. They do not certify repair completion,
OEM compliance, or repair quality.
"""
from __future__ import annotations

from typing import Any

from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.ar_payload import build_ar_workflow_payload
from repairgraph.state.events import (
    action_completed_event,
    action_started_event,
    blocker_resolved_event,
    phase_started_event,
    qa_gate_passed_event,
    session_started_event,
)
from repairgraph.state.export_json import export_state_to_dict
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.project import project_repair_state
from repairgraph.state.schema import RepairState


def build_accord_initial_state() -> RepairState:
    """Load 2025 Honda Accord procedure and initialize a fresh RepairState."""
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


def build_accord_demo_events(initial_state: RepairState) -> list:
    """Build a deterministic sample event ledger for the Accord demo.

    Uses fixed event IDs and timestamps so every run produces identical output.
    """
    events = []

    events.append(
        session_started_event(
            session_id=initial_state.session.session_id,
            actor="advisor",
            event_id="evt_demo_session_started",
            timestamp="2026-01-01T09:00:00Z",
        )
    )

    # Prefer "component_replacement" (phase 3), then first phase with pending actions.
    demo_phase = None
    for phase in initial_state.phases:
        if phase.name == "component_replacement":
            demo_phase = phase
            break
    if demo_phase is None:
        for phase in initial_state.phases:
            if phase.phase == 3:
                demo_phase = phase
                break
    if demo_phase is None:
        for phase in initial_state.phases:
            if phase.pending_actions:
                demo_phase = phase
                break
    if demo_phase is None and initial_state.phases:
        demo_phase = initial_state.phases[0]

    if demo_phase is not None:
        events.append(
            phase_started_event(
                phase_id=demo_phase.name,
                actor="advisor",
                event_id="evt_demo_phase_started",
                timestamp="2026-01-01T09:05:00Z",
            )
        )

        demo_action = next(
            (a for a in initial_state.actions if a.phase == demo_phase.phase),
            None,
        )

        if demo_action is not None:
            events.append(
                action_started_event(
                    action_id=demo_action.action_id,
                    actor="technician",
                    event_id="evt_demo_action_started",
                    timestamp="2026-01-01T09:10:00Z",
                )
            )
            events.append(
                action_completed_event(
                    action_id=demo_action.action_id,
                    actor="technician",
                    event_id="evt_demo_action_completed",
                    timestamp="2026-01-01T09:30:00Z",
                )
            )

    if initial_state.qa_gates:
        events.append(
            qa_gate_passed_event(
                gate_id=initial_state.qa_gates[0].gate_id,
                actor="inspector",
                event_id="evt_demo_qa_passed",
                timestamp="2026-01-01T10:00:00Z",
            )
        )

    if initial_state.blockers:
        events.append(
            blocker_resolved_event(
                blocker_id=initial_state.blockers[0].blocker_id,
                actor="advisor",
                event_id="evt_demo_blocker_resolved",
                timestamp="2026-01-01T10:05:00Z",
            )
        )

    return events


def build_accord_projected_state() -> RepairState:
    """Return the Accord state after applying the deterministic demo event ledger."""
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    return project_repair_state(initial, events)


def build_accord_ar_payload() -> dict[str, Any]:
    """Return the AR workflow payload for the deterministic Accord projected state."""
    projected = build_accord_projected_state()
    return build_ar_workflow_payload(projected)
