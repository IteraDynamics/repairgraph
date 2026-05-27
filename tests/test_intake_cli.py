"""
Tests for repairgraph.intake.cli.

Verifies CLI output, file writing, path collection, and terminal summary.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from repairgraph.intake.cli import (
    MANIFEST_FILENAME,
    REPORT_FILENAME,
    _OUTPUT_DIR,
    collect_paths,
    run_intake_cli,
)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
FORD_PACKET = FIXTURES / "ford_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


class TestCliConstants:
    def test_manifest_filename(self):
        assert MANIFEST_FILENAME == "intake_manifest.json"

    def test_report_filename(self):
        assert REPORT_FILENAME == "intake_report.html"

    def test_output_dir_is_path(self):
        assert isinstance(_OUTPUT_DIR, Path)

    def test_output_dir_ends_with_intake(self):
        assert _OUTPUT_DIR.name == "intake"

    def test_output_dir_parent_is_extracted(self):
        assert _OUTPUT_DIR.parent.name == "extracted"


class TestCollectPaths:
    def test_directory_expands_to_files(self):
        paths = collect_paths([str(TOYOTA_PACKET)])
        assert len(paths) > 0
        for p in paths:
            assert p.is_file()

    def test_file_paths_returned_directly(self):
        f = TOYOTA_PACKET / "camry_repair_procedure.txt"
        paths = collect_paths([str(f)])
        assert len(paths) == 1
        assert paths[0] == f

    def test_nonexistent_path_skipped(self, tmp_path, capsys):
        paths = collect_paths([str(tmp_path / "does_not_exist")])
        assert paths == []

    def test_multiple_args(self):
        paths = collect_paths([str(TOYOTA_PACKET), str(FORD_PACKET)])
        assert len(paths) > 2

    def test_returns_list_of_path(self):
        paths = collect_paths([str(TOYOTA_PACKET)])
        for p in paths:
            assert isinstance(p, Path)


class TestRunIntakeCli:
    def test_no_args_prints_usage(self, capsys):
        run_intake_cli([])
        captured = capsys.readouterr()
        assert "Usage" in captured.out or "usage" in captured.out.lower()

    def test_no_args_does_not_crash(self):
        run_intake_cli([])

    def test_toyota_packet_runs(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path / "out"):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert "Toyota" in captured.out or "toyota" in captured.out.lower()

    def test_creates_output_dir(self, tmp_path):
        out_dir = tmp_path / "intake_out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        assert out_dir.is_dir()

    def test_writes_manifest_json(self, tmp_path):
        out_dir = tmp_path / "intake_out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        manifest_file = out_dir / MANIFEST_FILENAME
        assert manifest_file.exists()
        assert manifest_file.stat().st_size > 100

    def test_writes_html_report(self, tmp_path):
        out_dir = tmp_path / "intake_out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        report_file = out_dir / REPORT_FILENAME
        assert report_file.exists()
        assert report_file.stat().st_size > 1000

    def test_manifest_is_valid_json(self, tmp_path):
        import json
        out_dir = tmp_path / "intake_out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        content = (out_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")
        data = json.loads(content)
        assert "intake_id" in data
        assert "readiness" in data
        assert "files" in data

    def test_html_report_is_html(self, tmp_path):
        out_dir = tmp_path / "intake_out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        content = (out_dir / REPORT_FILENAME).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "RepairGraph" in content

    def test_prints_readiness(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert "Readiness" in captured.out or "readiness" in captured.out.lower()

    def test_prints_oem_detected(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert "OEM" in captured.out or "oem" in captured.out.lower()

    def test_prints_advisory(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert "Advisory" in captured.out or "advisory" in captured.out.lower()

    def test_prints_output_paths(self, tmp_path, capsys):
        out_dir = tmp_path / "out"
        with patch("repairgraph.intake.cli._OUTPUT_DIR", out_dir):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert MANIFEST_FILENAME in captured.out or "manifest" in captured.out.lower()
        assert REPORT_FILENAME in captured.out or "report" in captured.out.lower()

    def test_ford_packet_runs(self, tmp_path):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path / "out"):
            run_intake_cli([str(FORD_PACKET)])

    def test_mixed_packet_does_not_crash(self, tmp_path):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path / "out"):
            run_intake_cli([str(MIXED_PACKET)])

    def test_nonexistent_path_handled(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path / "out"):
            run_intake_cli([str(tmp_path / "does_not_exist")])
        # Should not crash

    def test_prints_file_count(self, tmp_path, capsys):
        with patch("repairgraph.intake.cli._OUTPUT_DIR", tmp_path):
            run_intake_cli([str(TOYOTA_PACKET)])
        captured = capsys.readouterr()
        assert "file" in captured.out.lower() or "File" in captured.out
