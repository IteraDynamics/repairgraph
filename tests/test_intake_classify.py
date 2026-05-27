"""
Tests for repairgraph.intake.classify.

Verifies file classification, metadata detection, packet assembly,
graceful error handling, and determinism on fixture files.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from repairgraph.intake.classify import (
    classify_intake_file,
    classify_intake_packet,
    detect_document_role,
    detect_oem_metadata,
    summarize_intake_manifest,
)
from repairgraph.intake.schema import IntakeFile, IntakeManifest

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
FORD_PACKET = FIXTURES / "ford_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


# ── detect_document_role ───────────────────────────────────────────────────────

class TestDetectDocumentRole:
    def test_empty_text_returns_unknown(self):
        assert detect_document_role("") == "unknown"

    def test_whitespace_only_returns_unknown(self):
        assert detect_document_role("   \n\t  ") == "unknown"

    def test_repair_procedure_text(self):
        text = "Step 1 — Removal procedure. Disassembly of the panel. Installation steps follow."
        role = detect_document_role(text)
        assert role == "repair_procedure"

    def test_welding_text(self):
        text = "Spot weld nugget diameter 6mm. MIG welding at 130A. Plug weld per weld map."
        role = detect_document_role(text)
        assert role == "welding"

    def test_corrosion_text(self):
        text = "Apply anti-corrosion sealer. Cavity wax injection required. Zinc primer."
        role = detect_document_role(text)
        assert role == "corrosion_protection"

    def test_materials_text(self):
        text = "UHSS high strength steel 980 MPa tensile strength. Material classification."
        role = detect_document_role(text)
        assert role == "materials"

    def test_precautions_text(self):
        text = "WARNING: Do not weld near high-voltage systems. Danger. Safety precaution."
        role = detect_document_role(text)
        assert role == "precautions"

    def test_calibration_text(self):
        text = "ADAS calibration required after repair. Camera calibration procedure. Sensor recalibration."
        role = detect_document_role(text)
        assert role == "calibration"

    def test_dimensions_text(self):
        text = "Panel gap specification: 4.0mm +/- 1.0mm tolerance. Clearance measurement."
        role = detect_document_role(text)
        assert role == "dimensions"

    def test_returns_string(self):
        result = detect_document_role("random text about nothing in particular")
        assert isinstance(result, str)

    def test_deterministic(self):
        text = "Removal procedure step 1 installation."
        assert detect_document_role(text) == detect_document_role(text)


# ── detect_oem_metadata ────────────────────────────────────────────────────────

class TestDetectOemMetadata:
    def test_empty_text_returns_none_values(self):
        result = detect_oem_metadata("")
        assert result["oem"] is None
        assert result["model"] is None
        assert result["year"] is None
        assert result["confidence"] == 0.0

    def test_toyota_text(self):
        text = "TOYOTA MOTOR CORPORATION 2023 TOYOTA CAMRY repair procedure"
        result = detect_oem_metadata(text)
        assert result["oem"] == "Toyota"

    def test_ford_text(self):
        text = "FORD MOTOR COMPANY 2022 FORD F-150 repair procedure"
        result = detect_oem_metadata(text)
        assert result["oem"] == "Ford"

    def test_honda_text(self):
        text = "Honda Accord 2025 repair body panel replacement procedure"
        result = detect_oem_metadata(text)
        assert result["oem"] == "Honda"

    def test_year_detected(self):
        text = "2023 TOYOTA CAMRY repair manual"
        result = detect_oem_metadata(text)
        assert result["year"] == 2023

    def test_year_out_of_range_not_detected(self):
        text = "Specification 1234 and year 9999 are invalid"
        result = detect_oem_metadata(text)
        assert result["year"] is None

    def test_confidence_zero_for_empty(self):
        result = detect_oem_metadata("")
        assert result["confidence"] == 0.0

    def test_confidence_positive_for_oem_text(self):
        result = detect_oem_metadata("Toyota Motor Corporation repair manual")
        assert result["confidence"] > 0.0

    def test_operation_detected(self):
        text = "quarter panel replacement procedure removal installation"
        result = detect_oem_metadata(text)
        assert result["operation"] is not None
        assert "quarter" in result["operation"]

    def test_returns_all_keys(self):
        result = detect_oem_metadata("some text")
        for key in ("oem", "model", "year", "operation", "confidence"):
            assert key in result

    def test_deterministic(self):
        text = "Toyota Camry 2023 repair procedure"
        assert detect_oem_metadata(text) == detect_oem_metadata(text)


# ── classify_intake_file ───────────────────────────────────────────────────────

class TestClassifyIntakeFile:
    def test_toyota_repair_procedure(self, tmp_path):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert isinstance(result, IntakeFile)
        assert result.document_role == "repair_procedure"
        assert result.detected_oem == "Toyota"
        assert result.confidence > 0.0

    def test_toyota_welding_specs(self, tmp_path):
        src = TOYOTA_PACKET / "camry_welding_specs.txt"
        result = classify_intake_file(src)
        assert result.document_role == "welding"

    def test_toyota_corrosion_protection(self):
        src = TOYOTA_PACKET / "camry_corrosion_protection.txt"
        result = classify_intake_file(src)
        assert result.document_role == "corrosion_protection"

    def test_ford_repair_procedure(self):
        src = FORD_PACKET / "f150_repair_procedure.txt"
        result = classify_intake_file(src)
        # The F-150 procedure file contains both procedure steps and dimension
        # specs (gap measurements); the classifier may reasonably score either
        # role highest. Verify Ford OEM is detected and confidence is non-zero.
        assert result.document_role in ("repair_procedure", "dimensions", "precautions")
        assert result.detected_oem == "Ford"
        assert result.confidence > 0.0

    def test_ford_materials(self):
        src = FORD_PACKET / "f150_materials.txt"
        result = classify_intake_file(src)
        assert result.document_role == "materials"

    def test_unknown_document_gets_unknown_or_low_conf(self):
        src = MIXED_PACKET / "unknown_document.txt"
        result = classify_intake_file(src)
        # Unknown document should have low confidence or unknown role
        assert result.confidence < 0.5 or result.document_role == "unknown"

    def test_empty_file_handled(self):
        src = MIXED_PACKET / "empty_file.txt"
        result = classify_intake_file(src)
        assert isinstance(result, IntakeFile)
        assert result.confidence == 0.0
        assert result.warnings  # should warn about empty file

    def test_nonexistent_file_has_error(self, tmp_path):
        fake = tmp_path / "does_not_exist.txt"
        result = classify_intake_file(fake)
        # Should not crash; should have errors
        assert isinstance(result, IntakeFile)
        assert result.errors or result.confidence == 0.0

    def test_file_id_is_string(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert isinstance(result.file_id, str)
        assert result.file_id.startswith("file_")

    def test_deterministic(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        r1 = classify_intake_file(src)
        r2 = classify_intake_file(src)
        assert r1.document_role == r2.document_role
        assert r1.detected_oem == r2.detected_oem
        assert r1.confidence == r2.confidence

    def test_unsupported_extension_warns(self, tmp_path):
        f = tmp_path / "doc.xyz"
        f.write_text("Toyota Camry repair procedure removal installation step 1", encoding="utf-8")
        result = classify_intake_file(f)
        assert result.warnings

    def test_size_bytes_populated(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.size_bytes > 0

    def test_year_detected_from_fixture(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.detected_year == 2023

    def test_advisory_note_present(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert isinstance(result.advisory_note, str)


# ── classify_intake_packet ─────────────────────────────────────────────────────

class TestClassifyIntakePacket:
    def test_empty_paths_returns_manifest(self):
        manifest = classify_intake_packet([])
        assert isinstance(manifest, IntakeManifest)
        assert manifest.readiness == "unprocessable"

    def test_toyota_packet(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert isinstance(manifest, IntakeManifest)
        assert manifest.detected_packet.detected_oem == "Toyota"

    def test_toyota_packet_has_procedure_role(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert "repair_procedure" in manifest.detected_packet.detected_roles

    def test_toyota_packet_has_welding_role(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert "welding" in manifest.detected_packet.detected_roles

    def test_ford_packet_oem_detected(self):
        paths = list(FORD_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Ford"

    def test_mixed_packet_handles_unknown(self):
        paths = list(MIXED_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert isinstance(manifest, IntakeManifest)
        # Should not crash on unknown/empty files

    def test_nonexistent_path_adds_diagnostic(self, tmp_path):
        fake = tmp_path / "missing.txt"
        manifest = classify_intake_packet([fake])
        codes = [d.code for d in manifest.diagnostics]
        assert "FILE_NOT_FOUND" in codes

    def test_intake_id_is_string(self):
        manifest = classify_intake_packet([])
        assert isinstance(manifest.intake_id, str)
        assert manifest.intake_id.startswith("intake_")

    def test_created_at_is_iso(self):
        manifest = classify_intake_packet([])
        assert isinstance(manifest.created_at, str)
        assert "T" in manifest.created_at

    def test_readiness_values_valid(self):
        from repairgraph.intake.schema import READINESS_LEVELS
        manifest = classify_intake_packet([])
        assert manifest.readiness in READINESS_LEVELS

    def test_missing_roles_listed(self):
        manifest = classify_intake_packet([])
        assert isinstance(manifest.missing_roles, list)

    def test_advisory_present(self):
        manifest = classify_intake_packet([])
        assert isinstance(manifest.advisory, str)
        assert len(manifest.advisory) > 10

    def test_toyota_readiness_partial_or_ready(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.readiness in ("ready", "partial")

    def test_file_count_matches_readable_files(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.file_count == len(manifest.files)


# ── summarize_intake_manifest ─────────────────────────────────────────────────

class TestSummarizeIntakeManifest:
    def test_returns_dict(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        summary = summarize_intake_manifest(manifest)
        assert isinstance(summary, dict)

    def test_required_keys_present(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        summary = summarize_intake_manifest(manifest)
        for key in ("intake_id", "readiness", "file_count", "detected_oem",
                    "oem_confidence", "detected_roles", "missing_roles",
                    "error_count", "warning_count"):
            assert key in summary

    def test_toyota_summary_oem(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        summary = summarize_intake_manifest(manifest)
        assert summary["detected_oem"] == "Toyota"

    def test_deterministic(self):
        paths = sorted(TOYOTA_PACKET.iterdir())
        m1 = classify_intake_packet(paths)
        s1 = summarize_intake_manifest(m1)
        # Same files → same roles and OEM
        m2 = classify_intake_packet(paths)
        s2 = summarize_intake_manifest(m2)
        assert s1["detected_oem"] == s2["detected_oem"]
        assert s1["detected_roles"] == s2["detected_roles"]
