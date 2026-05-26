"""Tests for the AR workflow payload CLI (repairgraph.state.ar_cli)."""
import json

import pytest

from repairgraph.state.ar_cli import run_ar_demo
from repairgraph.state.ar_payload import SCHEMA_NAME, SCHEMA_VERSION


def test_ar_cli_returns_dict(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    result = run_ar_demo(output_path=str(output_file))
    assert isinstance(result, dict)


def test_ar_cli_writes_output_file(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    run_ar_demo(output_path=str(output_file))
    assert output_file.exists()


def test_ar_cli_output_is_valid_json(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    run_ar_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    assert isinstance(payload, dict)


def test_ar_cli_output_schema_metadata(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    run_ar_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    assert payload["schema_name"] == SCHEMA_NAME
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["advisory"] is True
    assert payload["generated_by"] == "repairgraph.state.ar_payload"


def test_ar_cli_output_preserves_accord_session(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert payload["session"]["oem"] == "Honda"
    assert payload["session"]["year"] == 2025
    assert payload["session"]["model"] == "Accord"


def test_ar_cli_output_session_is_in_progress(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert payload["session"]["status"] == "in_progress"


def test_ar_cli_output_overlays_present(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for key in ("zones", "actions", "qa_gates", "blockers"):
        assert key in payload["overlays"], f"Missing overlays key: {key}"


def test_ar_cli_output_has_zone_overlays(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert len(payload["overlays"]["zones"]) > 0


def test_ar_cli_output_has_action_guidance(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert len(payload["overlays"]["actions"]) > 0


def test_ar_cli_output_has_qa_gates(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert len(payload["overlays"]["qa_gates"]) > 0


def test_ar_cli_output_workflow_summary_present(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for key in ("phase_count", "action_count", "qa_gate_count", "blocker_count",
                "open_blocker_count", "event_count", "next_action_count"):
        assert key in payload["workflow_summary"], f"Missing workflow_summary key: {key}"


def test_ar_cli_output_active_context_present(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for key in ("active_phase_ids", "active_zone_ids", "blocked_phase_ids",
                "blocked_zone_ids", "next_action_ids"):
        assert key in payload["active_context"], f"Missing active_context key: {key}"


def test_ar_cli_output_source_state_present(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert payload["source_state"]["schema_name"] == "repairgraph.repair_state"
    assert payload["source_state"]["schema_version"] == "0.1"


def test_ar_cli_output_zone_overlays_have_required_fields(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for zone in payload["overlays"]["zones"]:
        for field in ("zone_id", "label", "status", "overlay_role"):
            assert field in zone, f"Zone overlay missing field: {field}"


def test_ar_cli_output_action_guidance_have_required_fields(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for action in payload["overlays"]["actions"]:
        for field in ("action_id", "action_type", "target", "phase",
                      "status", "guidance_role"):
            assert field in action, f"Action guidance missing field: {field}"


def test_ar_cli_output_qa_gates_have_required_fields(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    for gate in payload["overlays"]["qa_gates"]:
        for field in ("gate_id", "category", "priority", "status",
                      "blocks_completion", "guidance_role"):
            assert field in gate, f"QA gate item missing field: {field}"


def test_ar_cli_output_at_least_one_qa_gate_passed(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    passed = [g for g in payload["overlays"]["qa_gates"] if g["guidance_role"] == "passed_qa_gate"]
    assert len(passed) >= 1


def test_ar_cli_output_at_least_one_resolved_blocker(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    resolved = [b for b in payload["overlays"]["blockers"] if b["guidance_role"] == "resolved_blocker"]
    assert len(resolved) >= 1


def test_ar_cli_creates_parent_directories(tmp_path):
    nested_output = tmp_path / "deep" / "nested" / "ar_payload.json"
    run_ar_demo(output_path=str(nested_output))
    assert nested_output.exists()


def test_ar_cli_workflow_summary_counts_are_positive(tmp_path):
    output_file = tmp_path / "accord_ar_workflow_payload.json"
    payload = run_ar_demo(output_path=str(output_file))
    assert payload["workflow_summary"]["phase_count"] > 0
    assert payload["workflow_summary"]["action_count"] > 0
    assert payload["workflow_summary"]["qa_gate_count"] > 0
    assert payload["workflow_summary"]["event_count"] > 0
