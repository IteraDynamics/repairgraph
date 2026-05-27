"""
Tests for repairgraph.state.timeline — workflow timeline builders.
"""
from __future__ import annotations

import pytest

from repairgraph.state.demo import build_accord_initial_state, build_accord_projected_state
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
    summarize_timeline,
)


# ---------------------------------------------------------------------------
# build_event_timeline
# ---------------------------------------------------------------------------

def test_event_timeline_returns_list():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    assert isinstance(result, list)


def test_event_timeline_count_matches_events():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    assert len(result) == len(state.events)


def test_event_timeline_empty_when_no_events():
    state = build_accord_initial_state()
    result = build_event_timeline(state)
    assert result == []


def test_event_timeline_seq_starts_at_one():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    assert result[0]["seq"] == 1


def test_event_timeline_seq_is_contiguous():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    seqs = [e["seq"] for e in result]
    assert seqs == list(range(1, len(result) + 1))


def test_event_timeline_has_required_fields():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    required = {"seq", "event_id", "timestamp", "event_type", "actor", "target_type", "target_id"}
    for entry in result:
        assert required <= entry.keys()


def test_event_timeline_order_matches_event_ledger():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    event_ids = [e.event_id for e in state.events]
    timeline_ids = [entry["event_id"] for entry in result]
    assert timeline_ids == event_ids


def test_event_timeline_is_deterministic():
    r1 = build_event_timeline(build_accord_projected_state())
    r2 = build_event_timeline(build_accord_projected_state())
    assert r1 == r2


def test_event_timeline_entry_fields_match_event():
    state = build_accord_projected_state()
    result = build_event_timeline(state)
    for entry, event in zip(result, state.events):
        assert entry["event_id"] == event.event_id
        assert entry["event_type"] == event.event_type
        assert entry["actor"] == event.actor
        assert entry["target_type"] == event.target_type
        assert entry["target_id"] == event.target_id


# ---------------------------------------------------------------------------
# build_phase_timeline
# ---------------------------------------------------------------------------

def test_phase_timeline_returns_list():
    state = build_accord_projected_state()
    result = build_phase_timeline(state)
    assert isinstance(result, list)


def test_phase_timeline_count_matches_phases():
    state = build_accord_projected_state()
    result = build_phase_timeline(state)
    assert len(result) == len(state.phases)


def test_phase_timeline_ordered_by_phase_number():
    state = build_accord_projected_state()
    result = build_phase_timeline(state)
    phase_nums = [entry["phase"] for entry in result]
    assert phase_nums == sorted(phase_nums)


def test_phase_timeline_has_required_fields():
    state = build_accord_projected_state()
    result = build_phase_timeline(state)
    required = {"phase", "name", "label", "status", "active_zones",
                "completed_actions", "pending_actions", "blocked_by",
                "related_blockers", "advisory_notes"}
    for entry in result:
        assert required <= entry.keys()


def test_phase_timeline_is_deterministic():
    r1 = build_phase_timeline(build_accord_projected_state())
    r2 = build_phase_timeline(build_accord_projected_state())
    assert r1 == r2


def test_phase_timeline_statuses_are_strings():
    state = build_accord_projected_state()
    result = build_phase_timeline(state)
    for entry in result:
        assert isinstance(entry["status"], str)


# ---------------------------------------------------------------------------
# build_action_timeline
# ---------------------------------------------------------------------------

def test_action_timeline_returns_list():
    state = build_accord_projected_state()
    result = build_action_timeline(state)
    assert isinstance(result, list)


def test_action_timeline_count_matches_actions():
    state = build_accord_projected_state()
    result = build_action_timeline(state)
    assert len(result) == len(state.actions)


def test_action_timeline_has_required_fields():
    state = build_accord_projected_state()
    result = build_action_timeline(state)
    required = {"action_id", "phase", "action_type", "target", "status",
                "zone_refs", "requires_qa", "related_qa_gates"}
    for entry in result:
        assert required <= entry.keys()


def test_action_timeline_ordered_by_phase_then_id():
    state = build_accord_projected_state()
    result = build_action_timeline(state)
    phases = [entry["phase"] for entry in result]
    assert phases == sorted(phases)


def test_action_timeline_is_deterministic():
    r1 = build_action_timeline(build_accord_projected_state())
    r2 = build_action_timeline(build_accord_projected_state())
    assert r1 == r2


def test_action_timeline_no_qa_gates_when_requires_qa_false():
    state = build_accord_projected_state()
    result = build_action_timeline(state)
    for entry in result:
        if not entry["requires_qa"]:
            assert entry["related_qa_gates"] == []


# ---------------------------------------------------------------------------
# summarize_timeline
# ---------------------------------------------------------------------------

def test_summarize_timeline_returns_dict():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    assert isinstance(result, dict)


def test_summarize_timeline_has_required_keys():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    required = {
        "total_events", "phases", "actions",
        "open_qa_gates", "open_blockers", "next_actions",
        "advisory", "advisory_note",
    }
    assert required <= result.keys()


def test_summarize_timeline_event_count_matches():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    assert result["total_events"] == len(state.events)


def test_summarize_timeline_is_deterministic():
    s1 = summarize_timeline(build_accord_projected_state())
    s2 = summarize_timeline(build_accord_projected_state())
    assert s1 == s2


def test_summarize_timeline_advisory_flag():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    assert result["advisory"] is True


def test_summarize_timeline_no_events_initial():
    state = build_accord_initial_state()
    result = summarize_timeline(state)
    assert result["total_events"] == 0


def test_summarize_timeline_phases_dict():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    phases = result["phases"]
    assert "total" in phases
    assert "active" in phases
    assert "completed" in phases
    assert "blocked" in phases
    assert phases["total"] == len(state.phases)


def test_summarize_timeline_actions_dict():
    state = build_accord_projected_state()
    result = summarize_timeline(state)
    actions = result["actions"]
    assert "total" in actions
    assert "completed" in actions
    assert actions["total"] == len(state.actions)
