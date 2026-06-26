"""Tests for replay step enrichment."""
import pytest
from repairgraph.insights.replay_enrichment import enrich_replay_step


def _step(event_type, diff=None):
    return {
        "step": 1,
        "event": {
            "event_type": event_type,
            "actor": "tech1",
            "target_type": "phase",
            "timestamp": "2024-01-01T10:00:00",
        },
        "diff_summary": diff or {},
    }


def test_adds_significance_key():
    result = enrich_replay_step(_step("session_started"))
    assert "significance" in result


def test_preserves_original_keys():
    step = _step("action_completed")
    result = enrich_replay_step(step)
    assert result["step"] == 1
    assert result["event"]["event_type"] == "action_completed"


def test_does_not_mutate_input():
    step = _step("phase_started")
    original_keys = set(step.keys())
    enrich_replay_step(step)
    assert set(step.keys()) == original_keys


def test_known_event_types_have_significance():
    known_types = [
        "session_started", "phase_started", "phase_completed",
        "action_started", "action_completed", "action_blocked",
        "qa_gate_passed", "qa_gate_failed", "blocker_added",
        "blocker_resolved", "session_completed",
    ]
    for et in known_types:
        result = enrich_replay_step(_step(et))
        assert result["significance"], f"No significance for {et}"


def test_unknown_event_type_still_returns_significance():
    result = enrich_replay_step(_step("some_new_event_type"))
    assert "significance" in result
    assert result["significance"]


def test_diff_actions_appended():
    diff = {"actions_completed": ["replace_roof_panel", "spot_weld_b_pillar"], "changes": []}
    result = enrich_replay_step(_step("action_completed", diff=diff))
    sig = result["significance"]
    assert "replace_roof_panel" in sig or "spot_weld_b_pillar" in sig


def test_diff_blockers_resolved_appended():
    diff = {"blockers_resolved": ["blocker_qa_001"], "changes": []}
    result = enrich_replay_step(_step("blocker_resolved", diff=diff))
    assert "blocker_qa_001" in result["significance"]


def test_no_diff_still_works():
    result = enrich_replay_step(_step("phase_started", diff={}))
    assert result["significance"]
