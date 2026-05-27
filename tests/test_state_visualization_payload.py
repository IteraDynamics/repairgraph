"""
Tests for repairgraph.state.visualization_payload — combined visualization payload builder.
"""
from __future__ import annotations

import json

import pytest

from repairgraph.state.demo import build_accord_initial_state, build_accord_projected_state
from repairgraph.state.visualization_payload import build_workflow_visualization_payload


@pytest.fixture(scope="module")
def payload():
    state = build_accord_projected_state()
    return build_workflow_visualization_payload(state)


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------

def test_payload_is_dict(payload):
    assert isinstance(payload, dict)


def test_payload_is_json_serializable(payload):
    result = json.dumps(payload)
    assert isinstance(result, str)


def test_payload_schema_name(payload):
    assert payload["schema_name"] == "repairgraph.workflow_visualization"


def test_payload_schema_version(payload):
    assert payload["schema_version"] == "0.1"


def test_payload_advisory(payload):
    assert payload["advisory"] is True


def test_payload_advisory_note(payload):
    assert isinstance(payload["advisory_note"], str)
    assert len(payload["advisory_note"]) > 0


def test_payload_generated_by(payload):
    assert "repairgraph.state.visualization_payload" in payload["generated_by"]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def test_payload_session_has_required_fields(payload):
    session = payload["session"]
    for key in ("session_id", "oem", "year", "model", "operation", "status"):
        assert key in session


def test_payload_session_oem(payload):
    assert payload["session"]["oem"] == "Honda"


def test_payload_session_model(payload):
    assert payload["session"]["model"] == "Accord"


# ---------------------------------------------------------------------------
# Workflow summary
# ---------------------------------------------------------------------------

def test_payload_workflow_summary_present(payload):
    assert "workflow_summary" in payload


def test_payload_workflow_summary_fields(payload):
    ws = payload["workflow_summary"]
    for key in ("phase_count", "action_count", "qa_gate_count",
                "blocker_count", "open_blocker_count", "event_count", "next_action_count"):
        assert key in ws


def test_payload_event_count_positive(payload):
    assert payload["workflow_summary"]["event_count"] > 0


# ---------------------------------------------------------------------------
# Timelines
# ---------------------------------------------------------------------------

def test_payload_has_timelines(payload):
    assert "timelines" in payload


def test_payload_timelines_has_events(payload):
    assert "events" in payload["timelines"]
    assert isinstance(payload["timelines"]["events"], list)


def test_payload_timelines_has_phases(payload):
    assert "phases" in payload["timelines"]
    assert isinstance(payload["timelines"]["phases"], list)


def test_payload_timelines_has_actions(payload):
    assert "actions" in payload["timelines"]
    assert isinstance(payload["timelines"]["actions"], list)


def test_payload_timelines_has_summary(payload):
    assert "summary" in payload["timelines"]
    assert isinstance(payload["timelines"]["summary"], dict)


# ---------------------------------------------------------------------------
# Replay metadata
# ---------------------------------------------------------------------------

def test_payload_has_replay_metadata(payload):
    assert "replay_metadata" in payload


def test_payload_replay_metadata_fields(payload):
    rm = payload["replay_metadata"]
    for key in ("event_count", "snapshot_count", "event_ids", "event_types", "event_timestamps"):
        assert key in rm


def test_payload_replay_event_count_matches_events(payload):
    state = build_accord_projected_state()
    assert payload["replay_metadata"]["event_count"] == len(state.events)


# ---------------------------------------------------------------------------
# Visualization / Mermaid
# ---------------------------------------------------------------------------

def test_payload_has_visualization(payload):
    assert "visualization" in payload


def test_payload_visualization_sections(payload):
    sections = payload["visualization"]["sections"]
    assert "workflow_timeline" in sections
    assert "phase_flow" in sections
    assert "blocker_flow" in sections
    assert "zone_activation" in sections


def test_payload_mermaid_present(payload):
    assert "mermaid" in payload["visualization"]


def test_payload_mermaid_workflow_timeline(payload):
    mmd = payload["visualization"]["mermaid"]["workflow_timeline"]
    assert isinstance(mmd, str)
    assert "sequenceDiagram" in mmd


def test_payload_mermaid_phase_flow(payload):
    mmd = payload["visualization"]["mermaid"]["phase_flow"]
    assert isinstance(mmd, str)
    assert "flowchart" in mmd


def test_payload_mermaid_blocker_flow(payload):
    mmd = payload["visualization"]["mermaid"]["blocker_flow"]
    assert isinstance(mmd, str)
    assert "flowchart" in mmd


def test_payload_mermaid_zone_activation(payload):
    mmd = payload["visualization"]["mermaid"]["zone_activation"]
    assert isinstance(mmd, str)
    assert "flowchart" in mmd


# ---------------------------------------------------------------------------
# Active context
# ---------------------------------------------------------------------------

def test_payload_active_context_present(payload):
    assert "active_context" in payload


def test_payload_active_context_fields(payload):
    ctx = payload["active_context"]
    for key in ("active_phase_ids", "blocked_phase_ids",
                "active_zone_ids", "blocked_zone_ids", "next_action_ids"):
        assert key in ctx


# ---------------------------------------------------------------------------
# Blockers and next actions
# ---------------------------------------------------------------------------

def test_payload_has_blockers(payload):
    assert "blockers" in payload


def test_payload_blockers_is_dict(payload):
    assert isinstance(payload["blockers"], dict)


def test_payload_has_next_actions(payload):
    assert "next_actions" in payload


def test_payload_next_actions_is_dict(payload):
    assert isinstance(payload["next_actions"], dict)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_payload_is_deterministic():
    p1 = build_workflow_visualization_payload(build_accord_projected_state())
    p2 = build_workflow_visualization_payload(build_accord_projected_state())
    assert p1 == p2


def test_payload_initial_state_has_no_events():
    state = build_accord_initial_state()
    payload = build_workflow_visualization_payload(state)
    assert payload["workflow_summary"]["event_count"] == 0
    assert payload["timelines"]["events"] == []
