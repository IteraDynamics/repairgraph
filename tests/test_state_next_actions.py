import pytest

from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.events import (
    action_completed_event,
    action_started_event,
    session_started_event,
)
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.next_actions import (
    get_next_action_objects,
    get_next_actions,
    summarize_next_actions,
)
from repairgraph.state.project import project_repair_state
from repairgraph.state.schema import ActionState


def _accord_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


# --- get_next_actions ---

def test_get_next_actions_returns_list():
    state = _accord_state()
    result = get_next_actions(state)
    assert isinstance(result, list)


def test_get_next_actions_matches_state_attribute():
    state = _accord_state()
    result = get_next_actions(state)
    assert result == state.next_recommended_actions


def test_get_next_actions_is_list_on_initial_state():
    state = _accord_state()
    result = get_next_actions(state)
    assert isinstance(result, list)


def test_get_next_actions_returns_strings():
    state = _accord_state()
    result = get_next_actions(state)
    assert all(isinstance(action_id, str) for action_id in result)


def test_get_next_actions_does_not_mutate_state():
    state = _accord_state()
    original = list(state.next_recommended_actions)
    get_next_actions(state)
    assert state.next_recommended_actions == original


# --- get_next_action_objects ---

def test_get_next_action_objects_returns_list_of_action_states():
    state = _accord_state()
    result = get_next_action_objects(state)
    assert isinstance(result, list)
    assert all(isinstance(a, ActionState) for a in result)


def test_get_next_action_objects_ids_in_next_recommended():
    state = _accord_state()
    result = get_next_action_objects(state)
    for action in result:
        assert action.action_id in state.next_recommended_actions


def test_get_next_action_objects_is_list_on_initial_state():
    state = _accord_state()
    result = get_next_action_objects(state)
    assert isinstance(result, list)


def test_get_next_action_objects_count_matches_resolvable_ids():
    state = _accord_state()
    action_map = {a.action_id for a in state.actions}
    expected_count = sum(
        1 for aid in state.next_recommended_actions if aid in action_map
    )
    result = get_next_action_objects(state)
    assert len(result) == expected_count


def test_get_next_action_objects_does_not_mutate_state():
    state = _accord_state()
    original_count = len(state.next_recommended_actions)
    get_next_action_objects(state)
    assert len(state.next_recommended_actions) == original_count


def test_get_next_action_objects_ids_match_get_next_actions():
    state = _accord_state()
    next_ids = get_next_actions(state)
    objects = get_next_action_objects(state)
    resolved_ids = [a.action_id for a in objects]
    assert resolved_ids == next_ids[: len(resolved_ids)]


# --- summarize_next_actions ---

def test_summarize_next_actions_returns_dict():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert isinstance(result, dict)


def test_summarize_next_actions_required_keys():
    state = _accord_state()
    result = summarize_next_actions(state)
    for key in (
        "next_action_count",
        "next_action_ids",
        "next_action_targets",
        "current_phase",
        "phase_blocked",
        "session_completion_blocked",
        "advisory",
        "advisory_note",
    ):
        assert key in result, f"Missing key: {key}"


def test_summarize_next_actions_advisory_flag():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert result["advisory"] is True


def test_summarize_next_actions_count_matches_objects():
    state = _accord_state()
    result = summarize_next_actions(state)
    objects = get_next_action_objects(state)
    assert result["next_action_count"] == len(objects)


def test_summarize_next_actions_ids_match_objects():
    state = _accord_state()
    result = summarize_next_actions(state)
    objects = get_next_action_objects(state)
    assert result["next_action_ids"] == [a.action_id for a in objects]


def test_summarize_next_actions_targets_are_strings():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert all(isinstance(t, str) for t in result["next_action_targets"])


def test_summarize_next_actions_session_completion_blocked_true():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert result["session_completion_blocked"] is True


def test_summarize_next_actions_advisory_note_is_string():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert isinstance(result["advisory_note"], str)
    assert len(result["advisory_note"]) > 10


def test_summarize_next_actions_does_not_mutate_state():
    state = _accord_state()
    original_count = len(state.next_recommended_actions)
    summarize_next_actions(state)
    assert len(state.next_recommended_actions) == original_count


def test_summarize_next_actions_phase_blocked_false_on_initial():
    state = _accord_state()
    result = summarize_next_actions(state)
    # Initial state has no started phases, so phase_blocked should be False
    assert result["phase_blocked"] is False


def test_summarize_next_actions_current_phase_is_int_or_none():
    state = _accord_state()
    result = summarize_next_actions(state)
    assert result["current_phase"] is None or isinstance(result["current_phase"], int)


# --- integration: next actions after events ---

def test_next_actions_exclude_completed_action():
    state = _accord_state()
    if not state.actions:
        pytest.skip("No actions in initial state")

    # Use the first action directly (regardless of next_recommended_actions)
    first_id = state.actions[0].action_id

    projected = project_repair_state(
        state,
        [
            session_started_event(
                session_id=state.session.session_id,
                actor="advisor",
                event_id="evt_sess",
                timestamp="2026-01-01T09:00:00Z",
            ),
            action_started_event(
                action_id=first_id,
                actor="technician",
                event_id="evt_start",
                timestamp="2026-01-01T09:05:00Z",
            ),
            action_completed_event(
                action_id=first_id,
                actor="technician",
                event_id="evt_done",
                timestamp="2026-01-01T09:30:00Z",
            ),
        ],
    )

    projected_next = get_next_actions(projected)
    # A completed action should not appear in next recommended actions
    assert first_id not in projected_next
