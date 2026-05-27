"""
Tests for repairgraph.state.report_cli.

Verifies that the CLI generates expected HTML files, prints a summary, and
writes output to the correct location.
"""
from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from repairgraph.state.report_cli import (
    REPLAY_FILENAME,
    WORKFLOW_FILENAME,
    _OUTPUT_DIR,
    run_report_cli,
)


class TestReportCliConstants:
    def test_workflow_filename(self):
        assert WORKFLOW_FILENAME == "accord_workflow_report.html"

    def test_replay_filename(self):
        assert REPLAY_FILENAME == "accord_replay_report.html"

    def test_output_dir_is_path(self):
        assert isinstance(_OUTPUT_DIR, Path)

    def test_output_dir_ends_with_state(self):
        assert _OUTPUT_DIR.name == "state"

    def test_output_dir_parent_is_extracted(self):
        assert _OUTPUT_DIR.parent.name == "extracted"


class TestRunReportCli:
    def test_creates_output_directory(self, tmp_path):
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", tmp_path / "out" / "state"):
            run_report_cli()
        assert (tmp_path / "out" / "state").is_dir()

    def test_writes_workflow_html(self, tmp_path):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        workflow_file = out_dir / WORKFLOW_FILENAME
        assert workflow_file.exists()
        assert workflow_file.stat().st_size > 1000

    def test_writes_replay_html(self, tmp_path):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        replay_file = out_dir / REPLAY_FILENAME
        assert replay_file.exists()
        assert replay_file.stat().st_size > 1000

    def test_workflow_html_content(self, tmp_path):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        content = (out_dir / WORKFLOW_FILENAME).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "RepairGraph" in content
        assert "Accord" in content

    def test_replay_html_content(self, tmp_path):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        content = (out_dir / REPLAY_FILENAME).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Replay" in content
        assert "Accord" in content

    def test_prints_summary(self, tmp_path, capsys):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        captured = capsys.readouterr()
        assert "phases" in captured.out
        assert "blockers" in captured.out or "blocker" in captured.out
        assert "events" in captured.out
        assert "snapshots" in captured.out or "replay" in captured.out.lower()

    def test_prints_output_paths(self, tmp_path, capsys):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        captured = capsys.readouterr()
        assert "workflow" in captured.out.lower() or WORKFLOW_FILENAME in captured.out
        assert "replay" in captured.out.lower() or REPLAY_FILENAME in captured.out

    def test_idempotent_reruns(self, tmp_path):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
            first_workflow = (out_dir / WORKFLOW_FILENAME).read_text(encoding="utf-8")
            first_replay = (out_dir / REPLAY_FILENAME).read_text(encoding="utf-8")
            run_report_cli()
            second_workflow = (out_dir / WORKFLOW_FILENAME).read_text(encoding="utf-8")
            second_replay = (out_dir / REPLAY_FILENAME).read_text(encoding="utf-8")
        assert first_workflow == second_workflow
        assert first_replay == second_replay

    def test_prints_advisory_note(self, tmp_path, capsys):
        out_dir = tmp_path / "state"
        with patch("repairgraph.state.report_cli._OUTPUT_DIR", out_dir):
            run_report_cli()
        captured = capsys.readouterr()
        assert "advisory" in captured.out.lower() or "Advisory" in captured.out
