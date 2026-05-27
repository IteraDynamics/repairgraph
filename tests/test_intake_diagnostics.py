"""
Tests for repairgraph.intake.diagnostics.

Verifies completeness validation, missing role detection, diagnostic
structuring, and explainability of intake outputs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from repairgraph.intake.classify import classify_intake_packet
from repairgraph.intake.diagnostics import (
    ESSENTIAL_ROLES,
    RECOMMENDED_ROLES,
    ROLE_DESCRIPTIONS,
    build_intake_diagnostics,
    build_missing_role_report,
    validate_packet_completeness,
)
from repairgraph.intake.schema import IntakeDiagnostic, IntakeManifest, IntakePacket

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


def _make_empty_manifest(readiness: str = "incomplete") -> IntakeManifest:
    return IntakeManifest(intake_id="test_intake", readiness=readiness)


def _make_toyota_manifest() -> IntakeManifest:
    paths = list(TOYOTA_PACKET.iterdir())
    return classify_intake_packet(paths)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestDiagnosticsConstants:
    def test_essential_roles_contains_repair_procedure(self):
        assert "repair_procedure" in ESSENTIAL_ROLES

    def test_recommended_roles_nonempty(self):
        assert len(RECOMMENDED_ROLES) > 0

    def test_role_descriptions_covers_expected(self):
        for role in ("repair_procedure", "welding", "corrosion_protection", "materials"):
            assert role in ROLE_DESCRIPTIONS
            assert isinstance(ROLE_DESCRIPTIONS[role], str)
            assert len(ROLE_DESCRIPTIONS[role]) > 5


# ── validate_packet_completeness ──────────────────────────────────────────────

class TestValidatePacketCompleteness:
    def test_empty_manifest_returns_empty_packet_diagnostic(self):
        manifest = _make_empty_manifest()
        diags = validate_packet_completeness(manifest)
        codes = [d.code for d in diags]
        assert "EMPTY_PACKET" in codes

    def test_missing_essential_role_is_error(self):
        manifest = _make_empty_manifest()
        manifest.detected_packet.detected_roles.clear()
        diags = validate_packet_completeness(manifest)
        error_codes = [d.code for d in diags if d.severity == "error"]
        # EMPTY_PACKET takes priority and short-circuits — test with files
        # Use a manifest with files but no repair_procedure role
        from repairgraph.intake.schema import IntakeFile
        f = IntakeFile(file_id="x", filename="x.txt", extension=".txt", size_bytes=100,
                       document_role="welding", confidence=0.5)
        manifest2 = IntakeManifest(intake_id="t2", files=[f])
        diags2 = validate_packet_completeness(manifest2)
        error_codes2 = [d.code for d in diags2 if d.severity == "error"]
        assert any("MISSING_ESSENTIAL" in c for c in error_codes2)

    def test_missing_recommended_roles_are_warnings(self):
        from repairgraph.intake.schema import IntakeFile
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=100,
            document_role="repair_procedure", confidence=0.7,
        )
        manifest = IntakeManifest(intake_id="t", files=[f])
        diags = validate_packet_completeness(manifest)
        warning_codes = [d.code for d in diags if d.severity == "warning"]
        assert any("MISSING_RECOMMENDED" in c for c in warning_codes)

    def test_toyota_manifest_fewer_errors(self):
        manifest = _make_toyota_manifest()
        diags = validate_packet_completeness(manifest)
        errors = [d for d in diags if d.severity == "error"]
        # Toyota packet has repair_procedure so MISSING_ESSENTIAL should not appear
        error_codes = [d.code for d in errors]
        assert "MISSING_ESSENTIAL_REPAIR_PROCEDURE" not in error_codes

    def test_oem_not_detected_is_warning(self):
        from repairgraph.intake.schema import IntakeFile
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=100,
            document_role="repair_procedure", confidence=0.0,
        )
        manifest = IntakeManifest(intake_id="t", files=[f])
        diags = validate_packet_completeness(manifest)
        codes = [d.code for d in diags]
        assert "OEM_NOT_DETECTED" in codes

    def test_low_confidence_is_warning(self):
        from repairgraph.intake.schema import IntakeFile
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=100,
            document_role="repair_procedure", confidence=0.1,
        )
        manifest = IntakeManifest(
            intake_id="t", files=[f],
            detected_packet=IntakePacket(
                detected_oem="Toyota", oem_confidence=0.1,
                detected_roles=["repair_procedure"], file_count=1,
            )
        )
        diags = validate_packet_completeness(manifest)
        codes = [d.code for d in diags]
        assert "LOW_CONFIDENCE_CLASSIFICATIONS" in codes

    def test_returns_list_of_diagnostics(self):
        manifest = _make_toyota_manifest()
        diags = validate_packet_completeness(manifest)
        assert isinstance(diags, list)
        for d in diags:
            assert isinstance(d, IntakeDiagnostic)


# ── build_intake_diagnostics ──────────────────────────────────────────────────

class TestBuildIntakeDiagnostics:
    def test_returns_dict(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        assert isinstance(result, dict)

    def test_required_keys(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        for key in ("advisory", "readiness", "total_diagnostics", "error_count",
                    "warning_count", "info_count", "errors", "warnings", "infos",
                    "missing_essential_roles", "missing_recommended_roles", "found_roles"):
            assert key in result

    def test_advisory_is_true(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        assert result["advisory"] is True

    def test_counts_are_consistent(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        assert result["total_diagnostics"] == result["error_count"] + result["warning_count"] + result["info_count"]
        assert len(result["errors"]) == result["error_count"]
        assert len(result["warnings"]) == result["warning_count"]

    def test_found_roles_is_list(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        assert isinstance(result["found_roles"], list)

    def test_readiness_from_manifest(self):
        manifest = _make_toyota_manifest()
        result = build_intake_diagnostics(manifest)
        assert result["readiness"] == manifest.readiness

    def test_missing_essential_roles_list(self):
        manifest = _make_empty_manifest()
        result = build_intake_diagnostics(manifest)
        # Empty manifest has no files, so check structure
        assert isinstance(result["missing_essential_roles"], list)

    def test_diagnostic_dicts_have_required_keys(self):
        manifest = _make_empty_manifest()
        result = build_intake_diagnostics(manifest)
        all_diags = result["errors"] + result["warnings"] + result["infos"]
        for d in all_diags:
            assert "code" in d
            assert "severity" in d
            assert "message" in d


# ── build_missing_role_report ─────────────────────────────────────────────────

class TestBuildMissingRoleReport:
    def test_returns_dict(self):
        manifest = _make_toyota_manifest()
        result = build_missing_role_report(manifest)
        assert isinstance(result, dict)

    def test_required_keys(self):
        manifest = _make_toyota_manifest()
        result = build_missing_role_report(manifest)
        for key in ("found_roles", "missing_roles", "missing_essential",
                    "missing_recommended", "role_descriptions", "coverage_note", "advisory"):
            assert key in result

    def test_empty_manifest_has_all_missing(self):
        manifest = _make_empty_manifest()
        result = build_missing_role_report(manifest)
        assert "repair_procedure" in result["missing_essential"]

    def test_toyota_manifest_repair_procedure_found(self):
        manifest = _make_toyota_manifest()
        result = build_missing_role_report(manifest)
        assert "repair_procedure" in result["found_roles"]
        assert "repair_procedure" not in result["missing_roles"]

    def test_role_descriptions_for_missing(self):
        manifest = _make_empty_manifest()
        result = build_missing_role_report(manifest)
        for role in result["missing_roles"]:
            if role in result["role_descriptions"]:
                assert isinstance(result["role_descriptions"][role], str)

    def test_advisory_is_non_empty_string(self):
        manifest = _make_toyota_manifest()
        result = build_missing_role_report(manifest)
        assert isinstance(result["advisory"], str)
        assert len(result["advisory"]) > 10

    def test_coverage_note_mentions_counts(self):
        manifest = _make_toyota_manifest()
        result = build_missing_role_report(manifest)
        assert "role" in result["coverage_note"].lower() or "detected" in result["coverage_note"].lower()

    def test_missing_essential_subset_of_missing(self):
        manifest = _make_empty_manifest()
        result = build_missing_role_report(manifest)
        for r in result["missing_essential"]:
            assert r in result["missing_roles"]

    def test_missing_recommended_subset_of_missing(self):
        manifest = _make_empty_manifest()
        result = build_missing_role_report(manifest)
        for r in result["missing_recommended"]:
            assert r in result["missing_roles"]
