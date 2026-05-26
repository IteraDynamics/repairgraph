import json
from pathlib import Path

import pytest

from repairgraph.state.cli import run_demo
from repairgraph.state.schema import RepairState


def test_cli_run_demo_returns_repair_state(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    result = run_demo(output_path=str(output_file))
    assert isinstance(result, RepairState)


def test_cli_writes_output_file(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    run_demo(output_path=str(output_file))
    assert output_file.exists()


def test_cli_output_is_valid_json(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    run_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    assert isinstance(payload, dict)


def test_cli_output_has_required_metadata(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    run_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    assert payload["schema_name"] == "repairgraph.repair_state"
    assert payload["schema_version"] == "0.1"
    assert payload["advisory"] is True
    assert payload["generated_by"] == "repairgraph.state"


def test_cli_output_has_events(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    run_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    assert len(payload["events"]) > 0


def test_cli_output_session_is_in_progress(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    projected = run_demo(output_path=str(output_file))
    # session_started event should advance session to in_progress
    assert projected.session.status == "in_progress"


def test_cli_output_has_accord_session(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    projected = run_demo(output_path=str(output_file))
    assert projected.session.oem == "Honda"
    assert projected.session.year == 2025
    assert projected.session.model == "Accord"


def test_cli_output_action_started_and_completed(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    projected = run_demo(output_path=str(output_file))
    completed_actions = [a for a in projected.actions if a.status == "complete"]
    assert len(completed_actions) >= 1


def test_cli_output_qa_gate_passed(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    projected = run_demo(output_path=str(output_file))
    passed_gates = [g for g in projected.qa_gates if g.status == "passed"]
    assert len(passed_gates) >= 1


def test_cli_output_blocker_resolved(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    projected = run_demo(output_path=str(output_file))
    resolved_blockers = [b for b in projected.blockers if b.status == "resolved"]
    assert len(resolved_blockers) >= 1


def test_cli_creates_parent_directories(tmp_path):
    nested_output = tmp_path / "deep" / "nested" / "output.json"
    run_demo(output_path=str(nested_output))
    assert nested_output.exists()


def test_cli_output_preserves_all_state_sections(tmp_path):
    output_file = tmp_path / "accord_projected_state.json"
    run_demo(output_path=str(output_file))
    payload = json.loads(output_file.read_text())
    for key in ("session", "phases", "actions", "qa_gates", "zones",
                "blockers", "events", "next_recommended_actions", "interpretation_note"):
        assert key in payload, f"Missing section: {key}"
