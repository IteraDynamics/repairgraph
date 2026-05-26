import pytest

from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.blockers import (
    get_blockers_for_phase,
    get_open_blockers,
    get_session_completion_blockers,
    has_session_blockers,
    summarize_blockers,
)
from repairgraph.state.events import blocker_resolved_event
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.project import project_repair_state
from repairgraph.state.schema import Blocker


def _accord_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


# --- get_open_blockers ---

def test_get_open_blockers_returns_list_of_blockers():
    state = _accord_state()
    result = get_open_blockers(state)
    assert isinstance(result, list)
    assert all(isinstance(b, Blocker) for b in result)


def test_get_open_blockers_all_have_open_status():
    state = _accord_state()
    result = get_open_blockers(state)
    assert all(b.status == "open" for b in result)


def test_get_open_blockers_count_matches_state():
    state = _accord_state()
    expected = sum(1 for b in state.blockers if b.status == "open")
    assert len(get_open_blockers(state)) == expected


def test_get_open_blockers_decreases_after_resolve():
    state = _accord_state()
    if not state.blockers:
        pytest.skip("No blockers in initial state")

    blocker_id = state.blockers[0].blocker_id
    projected = project_repair_state(
        state,
        [
            blocker_resolved_event(
                blocker_id=blocker_id,
                actor="advisor",
                event_id="evt_test_resolve",
                timestamp="2026-01-01T10:00:00Z",
            )
        ],
    )

    original_open = len(get_open_blockers(state))
    projected_open = len(get_open_blockers(projected))
    assert projected_open == original_open - 1


def test_get_open_blockers_does_not_mutate_state():
    state = _accord_state()
    original_count = len(state.blockers)
    get_open_blockers(state)
    assert len(state.blockers) == original_count


# --- get_blockers_for_phase ---

def test_get_blockers_for_phase_returns_list():
    state = _accord_state()
    result = get_blockers_for_phase(state, "4")
    assert isinstance(result, list)


def test_get_blockers_for_phase_all_reference_phase():
    state = _accord_state()
    # Collect phase IDs referenced by any blocker
    phase_refs = set()
    for b in state.blockers:
        for block_ref in b.blocks:
            if block_ref.startswith("phase:"):
                phase_refs.add(block_ref[len("phase:"):])

    for phase_id in phase_refs:
        result = get_blockers_for_phase(state, phase_id)
        assert len(result) > 0
        for b in result:
            assert f"phase:{phase_id}" in b.blocks


def test_get_blockers_for_phase_bare_number_matches_prefixed():
    state = _accord_state()
    result_bare = get_blockers_for_phase(state, "4")
    result_prefixed = get_blockers_for_phase(state, "phase:4")
    assert result_bare == result_prefixed


def test_get_blockers_for_phase_only_open():
    state = _accord_state()
    result = get_blockers_for_phase(state, "4")
    assert all(b.status == "open" for b in result)


def test_get_blockers_for_phase_nonexistent_returns_empty():
    state = _accord_state()
    result = get_blockers_for_phase(state, "999")
    assert result == []


# --- get_session_completion_blockers ---

def test_get_session_completion_blockers_returns_list():
    state = _accord_state()
    result = get_session_completion_blockers(state)
    assert isinstance(result, list)


def test_get_session_completion_blockers_all_block_session():
    state = _accord_state()
    result = get_session_completion_blockers(state)
    for b in result:
        assert "session_completion" in b.blocks
        assert b.status == "open"


def test_get_session_completion_blockers_nonempty_on_initial_state():
    state = _accord_state()
    # Initial state has blocking QA gates → session blockers exist
    result = get_session_completion_blockers(state)
    assert len(result) > 0


# --- has_session_blockers ---

def test_has_session_blockers_true_on_initial_state():
    state = _accord_state()
    assert has_session_blockers(state) is True


def test_has_session_blockers_returns_bool():
    state = _accord_state()
    result = has_session_blockers(state)
    assert isinstance(result, bool)


def test_has_session_blockers_consistent_with_get():
    state = _accord_state()
    assert has_session_blockers(state) == bool(get_session_completion_blockers(state))


# --- summarize_blockers ---

def test_summarize_blockers_returns_dict():
    state = _accord_state()
    summary = summarize_blockers(state)
    assert isinstance(summary, dict)


def test_summarize_blockers_required_keys():
    state = _accord_state()
    summary = summarize_blockers(state)
    for key in (
        "total_blockers",
        "open_blockers",
        "resolved_blockers",
        "session_completion_blocked",
        "open_by_severity",
        "open_by_type",
        "open_blocker_ids",
        "session_blocker_ids",
    ):
        assert key in summary, f"Missing summary key: {key}"


def test_summarize_blockers_counts_add_up():
    state = _accord_state()
    summary = summarize_blockers(state)
    assert summary["total_blockers"] == len(state.blockers)
    assert summary["open_blockers"] + summary["resolved_blockers"] == summary["total_blockers"]


def test_summarize_blockers_session_completion_blocked_true():
    state = _accord_state()
    summary = summarize_blockers(state)
    assert summary["session_completion_blocked"] is True


def test_summarize_blockers_open_by_severity_values_are_lists():
    state = _accord_state()
    summary = summarize_blockers(state)
    for ids in summary["open_by_severity"].values():
        assert isinstance(ids, list)


def test_summarize_blockers_open_by_type_values_are_lists():
    state = _accord_state()
    summary = summarize_blockers(state)
    for ids in summary["open_by_type"].values():
        assert isinstance(ids, list)


def test_summarize_blockers_does_not_mutate_state():
    state = _accord_state()
    original_count = len(state.blockers)
    summarize_blockers(state)
    assert len(state.blockers) == original_count
