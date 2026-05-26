import pytest

from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.events import (
    action_blocked_event,
    action_completed_event,
    action_marked_not_applicable_event,
    action_started_event,
    blocker_resolved_event,
    phase_started_event,
    qa_gate_passed_event,
    session_cancelled_event,
    session_started_event,
)
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.project import project_repair_state


def _accord_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


def _first_action_id(state):
    return state.actions[0].action_id


def _first_gate_id(state):
    return state.qa_gates[0].gate_id


def _first_blocker_id(state):
    return state.blockers[0].blocker_id


def test_project_repair_state_does_not_mutate_initial_state():
    state = _accord_state()
    action_id = _first_action_id(state)

    projected = project_repair_state(
        state,
        [
            action_started_event(
                action_id=action_id,
                actor="technician",
                event_id="evt_action_started",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    assert state.actions[0].status == "pending"
    assert projected.actions[0].status == "in_progress"


def test_project_repair_state_appends_events_in_order():
    state = _accord_state()
    action_id = _first_action_id(state)

    events = [
        session_started_event(
            session_id=state.session.session_id,
            actor="advisor",
            event_id="evt_session_started",
            timestamp="2026-01-01T09:00:00Z",
        ),
        action_started_event(
            action_id=action_id,
            actor="technician",
            event_id="evt_action_started",
            timestamp="2026-01-01T10:00:00Z",
        ),
    ]

    projected = project_repair_state(state, events)

    assert [event.event_id for event in projected.events] == [
        "evt_session_started",
        "evt_action_started",
    ]


def test_session_started_sets_session_in_progress():
    state = _accord_state()

    projected = project_repair_state(
        state,
        [
            session_started_event(
                session_id=state.session.session_id,
                actor="advisor",
                event_id="evt_session_started",
                timestamp="2026-01-01T09:00:00Z",
            )
        ],
    )

    assert projected.session.status == "in_progress"


def test_phase_started_sets_phase_and_session_in_progress():
    state = _accord_state()

    projected = project_repair_state(
        state,
        [
            phase_started_event(
                phase_id="phase:3",
                actor="technician",
                event_id="evt_phase_started",
                timestamp="2026-01-01T09:00:00Z",
            )
        ],
    )

    phase = next(phase for phase in projected.phases if phase.phase == 3)

    assert phase.status == "in_progress"
    assert projected.session.status == "in_progress"


def test_action_started_sets_action_phase_session_and_zone_active():
    state = _accord_state()
    action = next(action for action in state.actions if action.zone_refs)

    projected = project_repair_state(
        state,
        [
            action_started_event(
                action_id=action.action_id,
                actor="technician",
                event_id="evt_action_started",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    projected_action = next(item for item in projected.actions if item.action_id == action.action_id)
    projected_phase = next(phase for phase in projected.phases if phase.phase == action.phase)
    projected_zone = next(zone for zone in projected.zones if zone.zone_id == action.zone_refs[0])

    assert projected_action.status == "in_progress"
    assert projected_phase.status == "in_progress"
    assert projected.session.status == "in_progress"
    assert projected_zone.status == "active"
    assert action.action_id in projected_zone.active_actions


def test_action_completed_moves_action_to_completed_actions():
    state = _accord_state()
    action_id = _first_action_id(state)

    projected = project_repair_state(
        state,
        [
            action_completed_event(
                action_id=action_id,
                actor="technician",
                event_id="evt_action_completed",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    action = next(action for action in projected.actions if action.action_id == action_id)
    phase = next(phase for phase in projected.phases if phase.phase == action.phase)

    assert action.status == "complete"
    assert action_id in phase.completed_actions
    assert action_id not in phase.pending_actions


def test_action_blocked_blocks_action_phase_session_and_zone():
    state = _accord_state()
    action = next(action for action in state.actions if action.zone_refs)

    projected = project_repair_state(
        state,
        [
            action_blocked_event(
                action_id=action.action_id,
                actor="technician",
                event_id="evt_action_blocked",
                timestamp="2026-01-01T10:00:00Z",
                notes="Waiting on structural confirmation.",
            )
        ],
    )

    projected_action = next(item for item in projected.actions if item.action_id == action.action_id)
    projected_phase = next(phase for phase in projected.phases if phase.phase == action.phase)
    projected_zone = next(zone for zone in projected.zones if zone.zone_id == action.zone_refs[0])

    assert projected_action.status == "blocked"
    assert projected_phase.status == "blocked"
    assert projected.session.status == "blocked"
    assert projected_zone.status == "blocked"


def test_action_marked_not_applicable_counts_as_completed_for_phase():
    state = _accord_state()
    action_id = _first_action_id(state)

    projected = project_repair_state(
        state,
        [
            action_marked_not_applicable_event(
                action_id=action_id,
                actor="technician",
                reason="Not applicable to selected repair scope.",
                event_id="evt_action_na",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    action = next(action for action in projected.actions if action.action_id == action_id)
    phase = next(phase for phase in projected.phases if phase.phase == action.phase)

    assert action.status == "not_applicable"
    assert action_id in phase.completed_actions
    assert action_id not in phase.pending_actions


def test_qa_gate_passed_updates_gate_status():
    state = _accord_state()
    gate_id = _first_gate_id(state)

    projected = project_repair_state(
        state,
        [
            qa_gate_passed_event(
                gate_id=gate_id,
                actor="technician",
                event_id="evt_qa_passed",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    gate = next(gate for gate in projected.qa_gates if gate.gate_id == gate_id)

    assert gate.status == "passed"


def test_blocker_resolved_updates_blocker_status():
    state = _accord_state()
    blocker_id = _first_blocker_id(state)

    projected = project_repair_state(
        state,
        [
            blocker_resolved_event(
                blocker_id=blocker_id,
                actor="technician",
                event_id="evt_blocker_resolved",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    blocker = next(blocker for blocker in projected.blockers if blocker.blocker_id == blocker_id)

    assert blocker.status == "resolved"


def test_next_recommended_actions_advances_after_completion():
    state = _accord_state()
    first_action = state.actions[0]

    projected = project_repair_state(
        state,
        [
            action_completed_event(
                action_id=first_action.action_id,
                actor="technician",
                event_id="evt_action_completed",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    assert first_action.action_id not in projected.next_recommended_actions


def test_unknown_action_target_raises():
    state = _accord_state()

    with pytest.raises(ValueError, match="Unknown action target"):
        project_repair_state(
            state,
            [
                action_completed_event(
                    action_id="replace_component:does_not_exist",
                    actor="technician",
                    event_id="evt_bad_action",
                    timestamp="2026-01-01T10:00:00Z",
                )
            ],
        )


def test_unknown_phase_target_raises():
    state = _accord_state()

    with pytest.raises(ValueError, match="Unknown phase target"):
        project_repair_state(
            state,
            [
                phase_started_event(
                    phase_id="phase:999",
                    actor="technician",
                    event_id="evt_bad_phase",
                    timestamp="2026-01-01T10:00:00Z",
                )
            ],
        )


def test_session_cancelled_event_sets_cancelled_status():
    state = _accord_state()

    projected = project_repair_state(
        state,
        [
            session_cancelled_event(
                session_id=state.session.session_id,
                actor="advisor",
                event_id="evt_session_cancelled",
                timestamp="2026-01-01T10:00:00Z",
                notes="Repair authorization withdrawn.",
            )
        ],
    )

    assert projected.session.status == "cancelled"
