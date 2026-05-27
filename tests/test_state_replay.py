"""
Tests for repairgraph.state.replay — state replay and diffing utilities.
"""
from __future__ import annotations

import pytest

from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.replay import (
    build_state_diff,
    replay_repair_state,
    summarize_state_diff,
)
from repairgraph.state.schema import RepairState


# ---------------------------------------------------------------------------
# replay_repair_state
# ---------------------------------------------------------------------------

def test_replay_returns_list():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    assert isinstance(result, list)


def test_replay_snapshot_count_equals_event_count():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    assert len(result) == len(events)


def test_replay_returns_repair_state_instances():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    for snap in result:
        assert isinstance(snap, RepairState)


def test_replay_empty_events_returns_empty_list():
    initial = build_accord_initial_state()
    result = replay_repair_state(initial, [])
    assert result == []


def test_replay_first_snapshot_has_one_event():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    assert len(result[0].events) == 1


def test_replay_last_snapshot_has_all_events():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    assert len(result[-1].events) == len(events)


def test_replay_snapshots_accumulate_events():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    for i, snap in enumerate(result):
        assert len(snap.events) == i + 1


def test_replay_last_snapshot_status_matches_projected():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    projected = build_accord_projected_state()
    assert result[-1].session.status == projected.session.status


def test_replay_does_not_mutate_initial_state():
    initial = build_accord_initial_state()
    original_status = initial.session.status
    original_event_count = len(initial.events)
    events = build_accord_demo_events(initial)
    replay_repair_state(initial, events)
    assert initial.session.status == original_status
    assert len(initial.events) == original_event_count


def test_replay_is_deterministic():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    r1 = replay_repair_state(initial, events)
    r2 = replay_repair_state(initial, events)
    assert len(r1) == len(r2)
    for s1, s2 in zip(r1, r2):
        assert s1.session.status == s2.session.status
        assert len(s1.events) == len(s2.events)


def test_replay_first_event_changes_session_status():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    result = replay_repair_state(initial, events)
    assert result[0].session.status != initial.session.status


# ---------------------------------------------------------------------------
# build_state_diff
# ---------------------------------------------------------------------------

def test_state_diff_returns_dict():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    assert isinstance(diff, dict)


def test_state_diff_empty_when_identical():
    state = build_accord_projected_state()
    diff = build_state_diff(state, state)
    assert diff == {}


def test_state_diff_detects_session_status_change():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    snapshots = replay_repair_state(initial, events)
    diff = build_state_diff(initial, snapshots[0])
    assert "session_status" in diff


def test_state_diff_session_status_shape():
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    snapshots = replay_repair_state(initial, events)
    diff = build_state_diff(initial, snapshots[0])
    assert "previous" in diff["session_status"]
    assert "current" in diff["session_status"]


def test_state_diff_detects_action_change():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    assert "actions" in diff


def test_state_diff_detects_qa_gate_change():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    assert "qa_gates" in diff


def test_state_diff_detects_blocker_change():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    assert "blockers" in diff


def test_state_diff_action_changes_shape():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    for action_id, change in diff["actions"].items():
        assert "previous_status" in change
        assert "current_status" in change


def test_state_diff_blocker_changes_shape():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    for blocker_id, change in diff["blockers"].items():
        assert "previous_status" in change
        assert "current_status" in change


def test_state_diff_does_not_mutate_inputs():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    initial_status_before = initial.session.status
    projected_status_before = projected.session.status
    build_state_diff(initial, projected)
    assert initial.session.status == initial_status_before
    assert projected.session.status == projected_status_before


# ---------------------------------------------------------------------------
# summarize_state_diff
# ---------------------------------------------------------------------------

def test_summarize_state_diff_returns_dict():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert isinstance(summary, dict)


def test_summarize_state_diff_has_required_keys():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    required = {
        "change_count", "changed_entities", "changes",
        "has_session_change", "has_phase_changes", "has_action_changes",
        "has_zone_changes", "has_qa_gate_changes", "has_blocker_changes",
        "has_next_action_changes",
    }
    assert required <= summary.keys()


def test_summarize_state_diff_detects_session_change():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert summary["has_session_change"] is True


def test_summarize_state_diff_detects_action_changes():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert summary["has_action_changes"] is True


def test_summarize_state_diff_detects_blocker_changes():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert summary["has_blocker_changes"] is True


def test_summarize_state_diff_change_count_positive():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert summary["change_count"] > 0


def test_summarize_state_diff_empty_diff():
    diff = {}
    summary = summarize_state_diff(diff)
    assert summary["change_count"] == 0
    assert summary["changed_entities"] == []
    assert summary["changes"] == []
    assert summary["has_session_change"] is False


def test_summarize_state_diff_changes_list():
    initial = build_accord_initial_state()
    projected = build_accord_projected_state()
    diff = build_state_diff(initial, projected)
    summary = summarize_state_diff(diff)
    assert isinstance(summary["changes"], list)
    assert len(summary["changes"]) > 0
