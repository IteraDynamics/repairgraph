"""
CLI demo: initialize a Honda 2025 Accord repair state, apply a deterministic
sample event ledger, project the resulting state, and export JSON.

Run:
    python -m repairgraph.state.cli
"""
from __future__ import annotations

import json
from pathlib import Path

from repairgraph.query.loader import load_procedure, load_vehicle_structure
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

DEFAULT_OUTPUT_PATH = "data/extracted/state/accord_projected_state.json"


def _build_sample_events(state: RepairState) -> list:
    """Build a deterministic sample event ledger for the Accord demo."""
    events = []

    events.append(
        session_started_event(
            session_id=state.session.session_id,
            actor="advisor",
            event_id="evt_demo_session_started",
            timestamp="2026-01-01T09:00:00Z",
        )
    )

    # Pick the demo phase: prefer "component_replacement" (typically phase 3),
    # then fall back to first phase with pending actions.
    demo_phase = None
    for phase in state.phases:
        if phase.name == "component_replacement":
            demo_phase = phase
            break
    if demo_phase is None:
        for phase in state.phases:
            if phase.phase == 3:
                demo_phase = phase
                break
    if demo_phase is None:
        for phase in state.phases:
            if phase.pending_actions:
                demo_phase = phase
                break
    if demo_phase is None and state.phases:
        demo_phase = state.phases[0]

    if demo_phase is not None:
        events.append(
            phase_started_event(
                phase_id=demo_phase.name,
                actor="advisor",
                event_id="evt_demo_phase_started",
                timestamp="2026-01-01T09:05:00Z",
            )
        )

        # First action in demo_phase
        demo_action = next(
            (a for a in state.actions if a.phase == demo_phase.phase),
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

    if state.qa_gates:
        events.append(
            qa_gate_passed_event(
                gate_id=state.qa_gates[0].gate_id,
                actor="inspector",
                event_id="evt_demo_qa_passed",
                timestamp="2026-01-01T10:00:00Z",
            )
        )

    if state.blockers:
        events.append(
            blocker_resolved_event(
                blocker_id=state.blockers[0].blocker_id,
                actor="advisor",
                event_id="evt_demo_blocker_resolved",
                timestamp="2026-01-01T10:05:00Z",
            )
        )

    return events


def run_demo(output_path: str = DEFAULT_OUTPUT_PATH) -> RepairState:
    """Initialize the Accord state, apply sample events, export JSON, and print summary.

    Returns the projected RepairState so callers can inspect it without re-running.
    """
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    initial_state = initialize_repair_state(procedure, structure)
    events = _build_sample_events(initial_state)
    projected = project_repair_state(initial_state, events)

    payload = export_state_to_dict(projected)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Output:                   {out}")
    print(f"Session:                  {projected.session.status} ({projected.session.session_id})")
    print(f"Phases:                   {len(projected.phases)}")
    print(f"Actions:                  {len(projected.actions)}")
    print(f"QA Gates:                 {len(projected.qa_gates)}")
    print(f"Blockers:                 {len(projected.blockers)}")
    print(f"Events applied:           {len(projected.events)}")
    print(f"Next recommended actions: {len(projected.next_recommended_actions)}")

    return projected


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
