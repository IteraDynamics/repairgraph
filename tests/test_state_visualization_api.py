"""
Tests for visualization API endpoints:
  GET /internal/state/accord/timeline
  GET /internal/state/accord/replay
  GET /internal/state/accord/visualization
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /internal/state/accord/timeline
# ---------------------------------------------------------------------------

def test_timeline_returns_200():
    assert client.get("/internal/state/accord/timeline").status_code == 200


def test_timeline_advisory():
    payload = client.get("/internal/state/accord/timeline").json()
    assert payload["advisory"] is True


def test_timeline_has_event_timeline():
    payload = client.get("/internal/state/accord/timeline").json()
    assert "event_timeline" in payload
    assert isinstance(payload["event_timeline"], list)


def test_timeline_event_timeline_non_empty():
    payload = client.get("/internal/state/accord/timeline").json()
    assert len(payload["event_timeline"]) > 0


def test_timeline_has_phase_timeline():
    payload = client.get("/internal/state/accord/timeline").json()
    assert "phase_timeline" in payload
    assert isinstance(payload["phase_timeline"], list)
    assert len(payload["phase_timeline"]) > 0


def test_timeline_has_action_timeline():
    payload = client.get("/internal/state/accord/timeline").json()
    assert "action_timeline" in payload
    assert isinstance(payload["action_timeline"], list)
    assert len(payload["action_timeline"]) > 0


def test_timeline_has_summary():
    payload = client.get("/internal/state/accord/timeline").json()
    assert "summary" in payload
    assert isinstance(payload["summary"], dict)


def test_timeline_schema_name():
    payload = client.get("/internal/state/accord/timeline").json()
    assert payload["schema_name"] == "repairgraph.repair_state.timeline"


def test_timeline_event_entries_have_seq():
    payload = client.get("/internal/state/accord/timeline").json()
    for entry in payload["event_timeline"]:
        assert "seq" in entry


def test_timeline_phase_entries_ordered():
    payload = client.get("/internal/state/accord/timeline").json()
    phases = [e["phase"] for e in payload["phase_timeline"]]
    assert phases == sorted(phases)


# ---------------------------------------------------------------------------
# GET /internal/state/accord/replay
# ---------------------------------------------------------------------------

def test_replay_returns_200():
    assert client.get("/internal/state/accord/replay").status_code == 200


def test_replay_advisory():
    payload = client.get("/internal/state/accord/replay").json()
    assert payload["advisory"] is True


def test_replay_schema_name():
    payload = client.get("/internal/state/accord/replay").json()
    assert payload["schema_name"] == "repairgraph.repair_state.replay"


def test_replay_has_ordered_snapshots():
    payload = client.get("/internal/state/accord/replay").json()
    assert "ordered_snapshots" in payload
    assert isinstance(payload["ordered_snapshots"], list)


def test_replay_snapshots_non_empty():
    payload = client.get("/internal/state/accord/replay").json()
    assert len(payload["ordered_snapshots"]) > 0


def test_replay_snapshots_ordered_by_step():
    payload = client.get("/internal/state/accord/replay").json()
    steps = [s["step"] for s in payload["ordered_snapshots"]]
    assert steps == list(range(1, len(steps) + 1))


def test_replay_has_event_count():
    payload = client.get("/internal/state/accord/replay").json()
    assert "event_count" in payload
    assert payload["event_count"] > 0


def test_replay_snapshot_count_matches_event_count():
    payload = client.get("/internal/state/accord/replay").json()
    assert payload["snapshot_count"] == payload["event_count"]
    assert len(payload["ordered_snapshots"]) == payload["snapshot_count"]


def test_replay_snapshots_have_event():
    payload = client.get("/internal/state/accord/replay").json()
    for snap in payload["ordered_snapshots"]:
        assert "event" in snap
        assert "event_type" in snap["event"]


def test_replay_snapshots_have_state_summary():
    payload = client.get("/internal/state/accord/replay").json()
    for snap in payload["ordered_snapshots"]:
        ss = snap["state_summary"]
        assert "session_status" in ss
        assert "next_recommended_actions" in ss


def test_replay_snapshots_have_diff():
    payload = client.get("/internal/state/accord/replay").json()
    for snap in payload["ordered_snapshots"]:
        assert "diff" in snap


def test_replay_snapshots_have_diff_summary():
    payload = client.get("/internal/state/accord/replay").json()
    for snap in payload["ordered_snapshots"]:
        ds = snap["diff_summary"]
        assert "change_count" in ds
        assert "changes" in ds


def test_replay_first_snapshot_changes_session():
    payload = client.get("/internal/state/accord/replay").json()
    first = payload["ordered_snapshots"][0]
    assert "session_status" in first["diff"]


# ---------------------------------------------------------------------------
# GET /internal/state/accord/visualization
# ---------------------------------------------------------------------------

def test_visualization_returns_200():
    assert client.get("/internal/state/accord/visualization").status_code == 200


def test_visualization_advisory():
    payload = client.get("/internal/state/accord/visualization").json()
    assert payload["advisory"] is True


def test_visualization_schema_name():
    payload = client.get("/internal/state/accord/visualization").json()
    assert payload["schema_name"] == "repairgraph.workflow_visualization"


def test_visualization_has_mermaid():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "visualization" in payload
    assert "mermaid" in payload["visualization"]


def test_visualization_mermaid_keys():
    payload = client.get("/internal/state/accord/visualization").json()
    mermaid = payload["visualization"]["mermaid"]
    for key in ("workflow_timeline", "phase_flow", "blocker_flow", "zone_activation"):
        assert key in mermaid
        assert isinstance(mermaid[key], str)
        assert len(mermaid[key]) > 0


def test_visualization_mermaid_workflow_timeline_syntax():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "sequenceDiagram" in payload["visualization"]["mermaid"]["workflow_timeline"]


def test_visualization_mermaid_phase_flow_syntax():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "flowchart" in payload["visualization"]["mermaid"]["phase_flow"]


def test_visualization_has_timelines():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "timelines" in payload
    assert "events" in payload["timelines"]


def test_visualization_has_active_context():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "active_context" in payload


def test_visualization_has_blockers():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "blockers" in payload


def test_visualization_has_next_actions():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "next_actions" in payload


def test_visualization_has_endpoint_advisory():
    payload = client.get("/internal/state/accord/visualization").json()
    assert "endpoint_advisory" in payload
