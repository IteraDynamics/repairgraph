"""
Tests for repairgraph.state.visualization_cli — visualization export CLI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from repairgraph.state.visualization_cli import run_visualization_cli


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------

def test_cli_returns_dict(tmp_path):
    result = run_visualization_cli(base_dir=tmp_path)
    assert isinstance(result, dict)


def test_cli_payload_schema_name(tmp_path):
    result = run_visualization_cli(base_dir=tmp_path)
    assert result["schema_name"] == "repairgraph.workflow_visualization"


def test_cli_payload_advisory(tmp_path):
    result = run_visualization_cli(base_dir=tmp_path)
    assert result["advisory"] is True


# ---------------------------------------------------------------------------
# File outputs
# ---------------------------------------------------------------------------

def test_cli_writes_json_file(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    assert (tmp_path / "accord_workflow_visualization.json").exists()


def test_cli_writes_timeline_mmd(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    assert (tmp_path / "accord_timeline.mmd").exists()


def test_cli_writes_phase_flow_mmd(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    assert (tmp_path / "accord_phase_flow.mmd").exists()


def test_cli_writes_blocker_flow_mmd(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    assert (tmp_path / "accord_blocker_flow.mmd").exists()


def test_cli_writes_zone_activation_mmd(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    assert (tmp_path / "accord_zone_activation.mmd").exists()


# ---------------------------------------------------------------------------
# JSON content
# ---------------------------------------------------------------------------

def test_cli_json_is_valid(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    content = (tmp_path / "accord_workflow_visualization.json").read_text(encoding="utf-8")
    payload = json.loads(content)
    assert isinstance(payload, dict)


def test_cli_json_has_schema_name(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    payload = json.loads(
        (tmp_path / "accord_workflow_visualization.json").read_text(encoding="utf-8")
    )
    assert payload["schema_name"] == "repairgraph.workflow_visualization"


def test_cli_json_has_mermaid_section(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    payload = json.loads(
        (tmp_path / "accord_workflow_visualization.json").read_text(encoding="utf-8")
    )
    assert "visualization" in payload
    assert "mermaid" in payload["visualization"]


def test_cli_json_has_timelines(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    payload = json.loads(
        (tmp_path / "accord_workflow_visualization.json").read_text(encoding="utf-8")
    )
    assert "timelines" in payload


# ---------------------------------------------------------------------------
# Mermaid file content
# ---------------------------------------------------------------------------

def test_cli_timeline_mmd_has_sequencediagram(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    content = (tmp_path / "accord_timeline.mmd").read_text(encoding="utf-8")
    assert "sequenceDiagram" in content


def test_cli_phase_flow_has_flowchart(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    content = (tmp_path / "accord_phase_flow.mmd").read_text(encoding="utf-8")
    assert "flowchart" in content


def test_cli_blocker_flow_has_flowchart(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    content = (tmp_path / "accord_blocker_flow.mmd").read_text(encoding="utf-8")
    assert "flowchart" in content


def test_cli_zone_activation_has_flowchart(tmp_path):
    run_visualization_cli(base_dir=tmp_path)
    content = (tmp_path / "accord_zone_activation.mmd").read_text(encoding="utf-8")
    assert "flowchart" in content


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def test_cli_creates_parent_directories(tmp_path):
    nested = tmp_path / "deep" / "nested" / "state"
    run_visualization_cli(base_dir=nested)
    assert (nested / "accord_workflow_visualization.json").exists()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_cli_json_output_is_deterministic(tmp_path):
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    run_visualization_cli(base_dir=out1)
    run_visualization_cli(base_dir=out2)
    p1 = json.loads((out1 / "accord_workflow_visualization.json").read_text())
    p2 = json.loads((out2 / "accord_workflow_visualization.json").read_text())
    assert p1 == p2
