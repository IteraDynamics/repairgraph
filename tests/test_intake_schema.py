"""
Tests for repairgraph.intake.schema.

Verifies dataclass construction, validation, constants, and defaults.
"""
from __future__ import annotations

import pytest

from repairgraph.intake.schema import (
    DIAGNOSTIC_SEVERITIES,
    DOCUMENT_ROLES,
    READINESS_LEVELS,
    SUPPORTED_EXTENSIONS,
    TEXT_EXTENSIONS,
    IntakeClassification,
    IntakeDiagnostic,
    IntakeFile,
    IntakeManifest,
    IntakePacket,
    IntakeSession,
    _INTAKE_ADVISORY,
)


class TestConstants:
    def test_document_roles_contains_expected(self):
        expected = {
            "repair_procedure", "sectioning", "welding", "corrosion_protection",
            "materials", "dimensions", "calibration", "precautions", "unknown",
        }
        assert expected == DOCUMENT_ROLES

    def test_readiness_levels(self):
        assert READINESS_LEVELS == {"ready", "partial", "incomplete", "unprocessable"}

    def test_diagnostic_severities(self):
        assert DIAGNOSTIC_SEVERITIES == {"info", "warning", "error"}

    def test_supported_extensions_contains_pdf_and_txt(self):
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS

    def test_text_extensions_subset_of_supported(self):
        assert TEXT_EXTENSIONS.issubset(SUPPORTED_EXTENSIONS)

    def test_advisory_is_string(self):
        assert isinstance(_INTAKE_ADVISORY, str)
        assert len(_INTAKE_ADVISORY) > 10


class TestIntakeFile:
    def test_minimal_construction(self):
        f = IntakeFile(file_id="file_abc", filename="test.txt", extension=".txt", size_bytes=100)
        assert f.file_id == "file_abc"
        assert f.filename == "test.txt"
        assert f.extension == ".txt"
        assert f.size_bytes == 100
        assert f.document_role == "unknown"
        assert f.confidence == 0.0

    def test_full_construction(self):
        f = IntakeFile(
            file_id="file_xyz",
            filename="procedure.txt",
            extension=".txt",
            size_bytes=5000,
            detected_oem="Toyota",
            detected_model="camry",
            detected_year=2023,
            detected_operation="quarter_panel_replacement",
            document_role="repair_procedure",
            confidence=0.75,
            warnings=["PDF heuristic"],
            errors=[],
        )
        assert f.detected_oem == "Toyota"
        assert f.detected_year == 2023
        assert f.document_role == "repair_procedure"
        assert f.confidence == 0.75

    def test_invalid_document_role_raises(self):
        with pytest.raises(ValueError, match="Invalid document_role"):
            IntakeFile(
                file_id="x", filename="x", extension=".txt", size_bytes=0,
                document_role="not_a_real_role",
            )

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            IntakeFile(
                file_id="x", filename="x", extension=".txt", size_bytes=0, confidence=1.5,
            )

    def test_confidence_negative_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            IntakeFile(
                file_id="x", filename="x", extension=".txt", size_bytes=0, confidence=-0.1,
            )

    def test_defaults_are_empty_lists(self):
        f = IntakeFile(file_id="x", filename="x.txt", extension=".txt", size_bytes=0)
        assert f.warnings == []
        assert f.errors == []

    def test_advisory_note_is_string(self):
        f = IntakeFile(file_id="x", filename="x.txt", extension=".txt", size_bytes=0)
        assert isinstance(f.advisory_note, str)


class TestIntakeDiagnostic:
    def test_construction(self):
        d = IntakeDiagnostic(code="TEST", severity="info", message="test message")
        assert d.code == "TEST"
        assert d.severity == "info"
        assert d.message == "test message"
        assert d.file_id is None
        assert d.detail is None

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Invalid diagnostic severity"):
            IntakeDiagnostic(code="X", severity="critical", message="x")

    def test_all_severities_valid(self):
        for sev in ("info", "warning", "error"):
            d = IntakeDiagnostic(code="X", severity=sev, message="x")
            assert d.severity == sev


class TestIntakePacket:
    def test_defaults(self):
        p = IntakePacket()
        assert p.detected_oem is None
        assert p.detected_model is None
        assert p.detected_year is None
        assert p.oem_confidence == 0.0
        assert p.detected_roles == []
        assert p.file_count == 0

    def test_full_construction(self):
        p = IntakePacket(
            detected_oem="Ford",
            detected_model=r"\bf-150\b",
            detected_year=2022,
            oem_confidence=0.72,
            detected_roles=["repair_procedure", "materials"],
            file_count=2,
        )
        assert p.detected_oem == "Ford"
        assert p.file_count == 2


class TestIntakeManifest:
    def test_minimal_construction(self):
        m = IntakeManifest(intake_id="intake_abc123")
        assert m.intake_id == "intake_abc123"
        assert m.files == []
        assert m.readiness == "incomplete"
        assert m.diagnostics == []
        assert m.missing_roles == []

    def test_invalid_readiness_raises(self):
        with pytest.raises(ValueError, match="Invalid readiness"):
            IntakeManifest(intake_id="x", readiness="excellent")

    def test_all_readiness_levels_valid(self):
        for r in ("ready", "partial", "incomplete", "unprocessable"):
            m = IntakeManifest(intake_id="x", readiness=r)
            assert m.readiness == r

    def test_advisory_is_non_empty(self):
        m = IntakeManifest(intake_id="x")
        assert isinstance(m.advisory, str)
        assert len(m.advisory) > 10


class TestIntakeSession:
    def test_construction(self):
        s = IntakeSession(
            session_id="sess_001",
            intake_id="intake_abc",
            created_at="2024-01-01T00:00:00Z",
            file_count=3,
        )
        assert s.session_id == "sess_001"
        assert s.file_count == 3
        assert s.source_paths == []


class TestIntakeClassification:
    def test_construction(self):
        f = IntakeFile(file_id="x", filename="x.txt", extension=".txt", size_bytes=0)
        c = IntakeClassification(
            file=f, role="welding", oem="Honda", model="accord", year=2025, confidence=0.8,
        )
        assert c.role == "welding"
        assert c.oem == "Honda"
        assert c.confidence == 0.8
