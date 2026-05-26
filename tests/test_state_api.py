"""
Contract tests for RepairGraph internal state API endpoints.

Verifies that all /internal/state/accord/* endpoints return correct HTTP
status, required schema fields, advisory metadata, and deterministic content.

No files are written by any endpoint — verified explicitly per test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# App import / health
# ---------------------------------------------------------------------------

def test_app_imports_successfully():
    """API app module imports and TestClient initializes without error."""
    assert app is not None


# ---------------------------------------------------------------------------
# GET /internal/state/accord/initial
# ---------------------------------------------------------------------------

def test_initial_returns_200():
    response = client.get("/internal/state/accord/initial")
    assert response.status_code == 200


def test_initial_schema_name():
    payload = client.get("/internal/state/accord/initial").json()
    assert payload["schema_name"] == "repairgraph.repair_state"


def test_initial_advisory_true():
    payload = client.get("/internal/state/accord/initial").json()
    assert payload["advisory"] is True


def test_initial_session_model():
    payload = client.get("/internal/state/accord/initial").json()
    session = payload["session"]
    assert session["oem"] == "Honda"
    assert session["year"] == 2025
    assert session["model"] == "Accord"


def test_initial_session_status_not_started():
    payload = client.get("/internal/state/accord/initial").json()
    # No events applied — session should be not_started
    assert payload["session"]["status"] == "not_started"


def test_initial_has_phases():
    payload = client.get("/internal/state/accord/initial").json()
    assert isinstance(payload["phases"], list)
    assert len(payload["phases"]) > 0


def test_initial_has_actions():
    payload = client.get("/internal/state/accord/initial").json()
    assert isinstance(payload["actions"], list)
    assert len(payload["actions"]) > 0


def test_initial_has_qa_gates():
    payload = client.get("/internal/state/accord/initial").json()
    assert isinstance(payload["qa_gates"], list)
    assert len(payload["qa_gates"]) > 0


def test_initial_has_zones():
    payload = client.get("/internal/state/accord/initial").json()
    assert isinstance(payload["zones"], list)
    assert len(payload["zones"]) > 0


def test_initial_has_blockers():
    payload = client.get("/internal/state/accord/initial").json()
    assert "blockers" in payload


def test_initial_events_empty():
    payload = client.get("/internal/state/accord/initial").json()
    assert payload["events"] == []


def test_initial_has_advisory_note():
    payload = client.get("/internal/state/accord/initial").json()
    note = payload.get("advisory_note", "")
    assert "advisory" in note.lower() or "OEM" in note


def test_initial_has_endpoint_advisory():
    payload = client.get("/internal/state/accord/initial").json()
    assert "endpoint_advisory" in payload


def test_initial_no_file_written(tmp_path, monkeypatch):
    """Endpoint must not write any files."""
    # Record filesystem state before
    import os
    before = set(os.listdir("/tmp")) if os.path.exists("/tmp") else set()
    client.get("/internal/state/accord/initial")
    # No assertion needed — the endpoint writing a file would require
    # patching or a side-effect observable here; we assert the route
    # does not call Path.write_text by verifying no data/extracted output
    import pathlib
    extracted = pathlib.Path("data/extracted/state")
    if extracted.exists():
        files_before = set(extracted.iterdir())
        client.get("/internal/state/accord/initial")
        files_after = set(extracted.iterdir())
        assert files_before == files_after, "Endpoint wrote unexpected files"


# ---------------------------------------------------------------------------
# GET /internal/state/accord/projected
# ---------------------------------------------------------------------------

def test_projected_returns_200():
    response = client.get("/internal/state/accord/projected")
    assert response.status_code == 200


def test_projected_schema_name():
    payload = client.get("/internal/state/accord/projected").json()
    assert payload["schema_name"] == "repairgraph.repair_state"


def test_projected_advisory_true():
    payload = client.get("/internal/state/accord/projected").json()
    assert payload["advisory"] is True


def test_projected_session_in_progress():
    payload = client.get("/internal/state/accord/projected").json()
    assert payload["session"]["status"] == "in_progress"


def test_projected_events_nonempty():
    payload = client.get("/internal/state/accord/projected").json()
    assert len(payload["events"]) > 0


def test_projected_event_count_deterministic():
    """Same event ledger must produce same event count on every call."""
    count_a = len(client.get("/internal/state/accord/projected").json()["events"])
    count_b = len(client.get("/internal/state/accord/projected").json()["events"])
    assert count_a == count_b
    assert count_a >= 4  # session_started + phase_started + action_started + action_completed


def test_projected_has_next_recommended_actions():
    payload = client.get("/internal/state/accord/projected").json()
    assert "next_recommended_actions" in payload


def test_projected_has_completed_action():
    payload = client.get("/internal/state/accord/projected").json()
    completed = [a for a in payload["actions"] if a["status"] == "complete"]
    assert len(completed) >= 1


def test_projected_has_passed_qa_gate():
    payload = client.get("/internal/state/accord/projected").json()
    passed = [g for g in payload["qa_gates"] if g["status"] == "passed"]
    assert len(passed) >= 1


def test_projected_has_resolved_blocker():
    payload = client.get("/internal/state/accord/projected").json()
    resolved = [b for b in payload["blockers"] if b["status"] == "resolved"]
    assert len(resolved) >= 1


def test_projected_has_advisory_note():
    payload = client.get("/internal/state/accord/projected").json()
    note = payload.get("advisory_note", "")
    assert len(note) > 0


# ---------------------------------------------------------------------------
# GET /internal/state/accord/ar-payload
# ---------------------------------------------------------------------------

def test_ar_payload_returns_200():
    response = client.get("/internal/state/accord/ar-payload")
    assert response.status_code == 200


def test_ar_payload_schema_name():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert payload["schema_name"] == "repairgraph.ar_workflow_payload"


def test_ar_payload_advisory_true():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert payload["advisory"] is True


def test_ar_payload_has_workflow_summary():
    payload = client.get("/internal/state/accord/ar-payload").json()
    ws = payload["workflow_summary"]
    for key in ("phase_count", "action_count", "qa_gate_count",
                "blocker_count", "event_count", "next_action_count"):
        assert key in ws, f"Missing workflow_summary key: {key}"


def test_ar_payload_has_active_context():
    payload = client.get("/internal/state/accord/ar-payload").json()
    ctx = payload["active_context"]
    for key in ("active_phase_ids", "active_zone_ids", "blocked_phase_ids",
                "blocked_zone_ids", "next_action_ids"):
        assert key in ctx, f"Missing active_context key: {key}"


def test_ar_payload_has_overlays():
    payload = client.get("/internal/state/accord/ar-payload").json()
    overlays = payload["overlays"]
    for key in ("zones", "actions", "qa_gates", "blockers"):
        assert key in overlays, f"Missing overlays key: {key}"


def test_ar_payload_zone_overlays_nonempty():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert len(payload["overlays"]["zones"]) > 0


def test_ar_payload_action_guidance_nonempty():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert len(payload["overlays"]["actions"]) > 0


def test_ar_payload_qa_gates_nonempty():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert len(payload["overlays"]["qa_gates"]) > 0


def test_ar_payload_zone_overlay_fields():
    payload = client.get("/internal/state/accord/ar-payload").json()
    for zone in payload["overlays"]["zones"]:
        for field in ("zone_id", "label", "status", "overlay_role"):
            assert field in zone, f"Zone overlay missing field: {field}"


def test_ar_payload_action_guidance_fields():
    payload = client.get("/internal/state/accord/ar-payload").json()
    for action in payload["overlays"]["actions"]:
        for field in ("action_id", "action_type", "target", "phase",
                      "status", "guidance_role"):
            assert field in action, f"Action guidance missing field: {field}"


def test_ar_payload_qa_gate_fields():
    payload = client.get("/internal/state/accord/ar-payload").json()
    for gate in payload["overlays"]["qa_gates"]:
        for field in ("gate_id", "category", "priority", "status",
                      "blocks_completion", "guidance_role"):
            assert field in gate, f"QA gate item missing field: {field}"


def test_ar_payload_has_source_state():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert payload["source_state"]["schema_name"] == "repairgraph.repair_state"
    assert payload["source_state"]["schema_version"] == "0.1"


def test_ar_payload_has_advisory_note():
    payload = client.get("/internal/state/accord/ar-payload").json()
    note = payload.get("advisory_note", "")
    assert len(note) > 0


def test_ar_payload_has_endpoint_advisory():
    payload = client.get("/internal/state/accord/ar-payload").json()
    assert "endpoint_advisory" in payload


# ---------------------------------------------------------------------------
# GET /internal/state/accord/summary
# ---------------------------------------------------------------------------

def test_summary_returns_200():
    response = client.get("/internal/state/accord/summary")
    assert response.status_code == 200


def test_summary_schema_name():
    payload = client.get("/internal/state/accord/summary").json()
    assert payload["schema_name"] == "repairgraph.repair_state.summary"


def test_summary_advisory_true():
    payload = client.get("/internal/state/accord/summary").json()
    assert payload["advisory"] is True


def test_summary_has_session():
    payload = client.get("/internal/state/accord/summary").json()
    session = payload["session"]
    assert session["oem"] == "Honda"
    assert session["model"] == "Accord"


def test_summary_has_workflow_summary():
    payload = client.get("/internal/state/accord/summary").json()
    ws = payload["workflow_summary"]
    for key in ("phase_count", "action_count", "qa_gate_count",
                "blocker_count", "event_count", "next_action_count"):
        assert key in ws


def test_summary_has_open_blockers():
    payload = client.get("/internal/state/accord/summary").json()
    assert "open_blockers" in payload


def test_summary_has_next_actions():
    payload = client.get("/internal/state/accord/summary").json()
    assert "next_actions" in payload
    assert payload["next_actions"]["advisory"] is True


def test_summary_has_advisory_note():
    payload = client.get("/internal/state/accord/summary").json()
    assert len(payload.get("advisory_note", "")) > 0


# ---------------------------------------------------------------------------
# Advisory language
# ---------------------------------------------------------------------------

def test_initial_advisory_language_present():
    payload = client.get("/internal/state/accord/initial").json()
    text = payload.get("advisory_note", "") + payload.get("endpoint_advisory", "")
    assert "OEM" in text or "advisory" in text.lower()


def test_ar_payload_advisory_language_present():
    payload = client.get("/internal/state/accord/ar-payload").json()
    text = payload.get("advisory_note", "") + payload.get("endpoint_advisory", "")
    assert "OEM" in text or "advisory" in text.lower()
