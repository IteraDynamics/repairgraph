"""
Tests for repairgraph.intake.evidence — Intake Evidence Inspector.

Covers:
- build_file_evidence: structure, JSON serializability, filename/text/breadcrumb/role evidence
- build_intake_evidence_payload: structure, all files included, JSON serializable
- summarize_role_coverage: primary roles, supporting roles, missing roles exclusion
- explain_file_classification: returns list of strings explaining classification
- Diagnostic codes: SPARSE_TEXT_EXTRACTION, ROLE_SCORE_BELOW_THRESHOLD, etc.
- Integration with classify_intake_packet and classify_intake_file
- API endpoint /internal/intake/evidence returns 200 JSON
- Regression: existing classify/report/upload tests still pass
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.intake.classify import classify_intake_file, classify_intake_packet
from repairgraph.intake.evidence import (
    DIAG_BREADCRUMB_EVIDENCE_FOUND,
    DIAG_FILENAME_ONLY_METADATA,
    DIAG_ROLE_COVERAGE_FROM_SUPPORTING,
    DIAG_ROLE_SCORE_BELOW_THRESHOLD,
    DIAG_SPARSE_TEXT_EXTRACTION,
    DIAG_SUPPORTING_ROLE_ONLY,
    build_file_evidence,
    build_intake_evidence_payload,
    explain_file_classification,
    summarize_role_coverage,
)
from repairgraph.intake.schema import IntakeFile, IntakeManifest, IntakePacket

client = TestClient(app)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
HYUNDAI_PACKET = FIXTURES / "hyundai_packet"
EVIDENCE_PACKET = FIXTURES / "evidence_packet"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_file(**kwargs) -> IntakeFile:
    defaults = {
        "file_id": "file_test",
        "filename": "test.txt",
        "extension": ".txt",
        "size_bytes": 100,
        "confidence": 0.5,
    }
    defaults.update(kwargs)
    return IntakeFile(**defaults)


def _evidence_packet_files() -> list[tuple]:
    files = []
    for f in sorted(EVIDENCE_PACKET.iterdir()):
        if f.is_file():
            files.append(("files", (f.name, f.read_bytes(), "text/plain")))
    return files


def _toyota_files() -> list[tuple]:
    files = []
    for f in sorted(TOYOTA_PACKET.iterdir()):
        if f.is_file():
            files.append(("files", (f.name, f.read_bytes(), "text/plain")))
    return files


# ── Fixture existence ─────────────────────────────────────────────────────────

class TestEvidenceFixtures:
    def test_evidence_packet_dir_exists(self):
        assert EVIDENCE_PACKET.exists(), f"Evidence fixture dir missing: {EVIDENCE_PACKET}"

    def test_procedure_with_supporting_exists(self):
        p = EVIDENCE_PACKET / "2023 Hyundai Elantra Quarter Panel Procedure with Welding and Corrosion.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_breadcrumb_fixture_exists(self):
        p = EVIDENCE_PACKET / "2023 Hyundai Elantra Weld Points Breadcrumb.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_sparse_fixture_exists(self):
        p = EVIDENCE_PACKET / "sparse_document.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_unknown_content_fixture_exists(self):
        p = EVIDENCE_PACKET / "unknown_content_no_oem.txt"
        assert p.exists(), f"Fixture missing: {p}"


# ── build_file_evidence structure ─────────────────────────────────────────────

class TestBuildFileEvidenceStructure:
    def test_returns_dict(self):
        f = _make_file()
        result = build_file_evidence(f)
        assert isinstance(result, dict)

    def test_required_top_level_keys(self):
        f = _make_file()
        result = build_file_evidence(f)
        for key in (
            "file_id", "filename", "extension", "size_bytes",
            "filename_evidence", "text_evidence", "breadcrumb_evidence",
            "role_evidence", "diagnostics_for_file", "classification_explanation",
        ):
            assert key in result, f"Missing key: {key}"

    def test_filename_evidence_keys(self):
        f = _make_file(filename="2023_Hyundai_Elantra_repair.txt")
        result = build_file_evidence(f)
        fn_ev = result["filename_evidence"]
        for key in (
            "parsed_oem_candidates", "parsed_model_candidates",
            "parsed_year_candidates", "parsed_operation_candidates",
            "filename_tokens",
        ):
            assert key in fn_ev, f"Missing filename_evidence key: {key}"

    def test_text_evidence_keys(self):
        f = _make_file()
        result = build_file_evidence(f)
        txt_ev = result["text_evidence"]
        for key in ("text_quality", "text_quality_reason", "has_role_signals", "role_signal_count"):
            assert key in txt_ev, f"Missing text_evidence key: {key}"

    def test_breadcrumb_evidence_keys(self):
        f = _make_file()
        result = build_file_evidence(f)
        bc_ev = result["breadcrumb_evidence"]
        for key in ("detected_breadcrumb_segments", "breadcrumb_count", "breadcrumbs_found"):
            assert key in bc_ev, f"Missing breadcrumb_evidence key: {key}"

    def test_role_evidence_keys(self):
        f = _make_file()
        result = build_file_evidence(f)
        role_ev = result["role_evidence"]
        for key in (
            "primary_role", "supporting_roles", "role_scores",
            "role_evidence_phrases", "confidence", "confidence_explanation",
        ):
            assert key in role_ev, f"Missing role_evidence key: {key}"

    def test_classification_explanation_is_list(self):
        f = _make_file()
        result = build_file_evidence(f)
        assert isinstance(result["classification_explanation"], list)

    def test_diagnostics_for_file_is_list(self):
        f = _make_file()
        result = build_file_evidence(f)
        assert isinstance(result["diagnostics_for_file"], list)


# ── JSON serializability ───────────────────────────────────────────────────────

class TestJsonSerializability:
    def test_file_evidence_is_json_serializable(self):
        f = _make_file(
            document_role="repair_procedure",
            supporting_roles=["welding"],
            role_scores={"repair_procedure": 1.0, "welding": 0.4},
            role_evidence=["removal and replacement", "[bc] weld points"],
        )
        result = build_file_evidence(f)
        # Must not raise
        serialized = json.dumps(result)
        assert len(serialized) > 10

    def test_evidence_payload_is_json_serializable(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        payload = build_intake_evidence_payload(manifest)
        serialized = json.dumps(payload)
        assert len(serialized) > 100

    def test_role_coverage_is_json_serializable(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        coverage = summarize_role_coverage(manifest)
        serialized = json.dumps(coverage)
        assert len(serialized) > 10

    def test_explain_file_classification_is_json_serializable(self):
        f = _make_file()
        result = explain_file_classification(f)
        assert isinstance(result, list)
        serialized = json.dumps(result)
        assert len(serialized) > 2


# ── Filename evidence ─────────────────────────────────────────────────────────

class TestFilenameEvidence:
    def test_filename_tokens_non_empty_for_named_file(self):
        f = _make_file(filename="2023_Hyundai_Elantra_repair.txt")
        ev = build_file_evidence(f)
        assert len(ev["filename_evidence"]["filename_tokens"]) > 0

    def test_oem_candidate_from_filename(self):
        f = _make_file(filename="2023_Hyundai_Elantra_repair.txt", detected_oem="Hyundai")
        ev = build_file_evidence(f)
        assert "Hyundai" in ev["filename_evidence"]["parsed_oem_candidates"]

    def test_model_candidate_from_filename(self):
        f = _make_file(filename="2023_Hyundai_Elantra_repair.txt", detected_model="Elantra")
        ev = build_file_evidence(f)
        assert "Elantra" in ev["filename_evidence"]["parsed_model_candidates"]

    def test_year_candidate_from_filename(self):
        f = _make_file(filename="2023_Hyundai_Elantra_repair.txt", detected_year=2023)
        ev = build_file_evidence(f)
        assert 2023 in ev["filename_evidence"]["parsed_year_candidates"]

    def test_no_oem_candidate_when_none(self):
        f = _make_file(filename="repair_procedure.txt", detected_oem=None)
        ev = build_file_evidence(f)
        assert ev["filename_evidence"]["parsed_oem_candidates"] == []

    def test_filename_includes_note(self):
        f = _make_file()
        ev = build_file_evidence(f)
        assert "note" in ev["filename_evidence"]


# ── Text evidence ─────────────────────────────────────────────────────────────

class TestTextEvidence:
    def test_text_quality_usable_when_role_scores_present(self):
        f = _make_file(role_scores={"repair_procedure": 1.0, "welding": 0.5})
        ev = build_file_evidence(f)
        assert ev["text_evidence"]["text_quality"] == "usable"

    def test_text_quality_none_for_error_file(self):
        f = _make_file(errors=["Could not read file: no such file"])
        ev = build_file_evidence(f)
        assert ev["text_evidence"]["text_quality"] == "none"

    def test_text_quality_sparse_when_no_role_scores(self):
        f = _make_file(role_scores={}, role_evidence=[])
        ev = build_file_evidence(f)
        assert ev["text_evidence"]["text_quality"] in ("sparse", "none")

    def test_text_quality_sparse_for_minimal_pdf_warning(self):
        f = _make_file(
            warnings=["PDF text extraction yielded minimal content. File may be image-only."],
        )
        ev = build_file_evidence(f)
        assert ev["text_evidence"]["text_quality"] == "sparse"

    def test_role_signal_count_matches_role_scores(self):
        f = _make_file(role_scores={"repair_procedure": 1.0, "welding": 0.5})
        ev = build_file_evidence(f)
        assert ev["text_evidence"]["role_signal_count"] == 2

    def test_text_evidence_has_quality_reason(self):
        f = _make_file()
        ev = build_file_evidence(f)
        assert isinstance(ev["text_evidence"]["text_quality_reason"], str)
        assert len(ev["text_evidence"]["text_quality_reason"]) > 5


# ── Breadcrumb evidence ────────────────────────────────────────────────────────

class TestBreadcrumbEvidence:
    def test_no_breadcrumbs_when_no_bc_evidence(self):
        f = _make_file(role_evidence=["removal and replacement", "weld points"])
        ev = build_file_evidence(f)
        assert ev["breadcrumb_evidence"]["breadcrumb_count"] == 0
        assert ev["breadcrumb_evidence"]["breadcrumbs_found"] is False

    def test_breadcrumbs_extracted_from_bc_tagged_evidence(self):
        f = _make_file(
            role_evidence=["removal and replacement", "[bc] weld points"],
            document_role="welding",
        )
        ev = build_file_evidence(f)
        assert ev["breadcrumb_evidence"]["breadcrumbs_found"] is True
        assert ev["breadcrumb_evidence"]["breadcrumb_count"] == 1
        assert "weld points" in ev["breadcrumb_evidence"]["detected_breadcrumb_segments"]

    def test_multiple_breadcrumbs_detected(self):
        f = _make_file(
            role_evidence=[
                "[bc] removal and replacement",
                "[bc] weld points",
                "corrosion protection",
            ],
            document_role="repair_procedure",
        )
        ev = build_file_evidence(f)
        assert ev["breadcrumb_evidence"]["breadcrumb_count"] == 2

    def test_breadcrumb_evidence_from_hyundai_weld_fixture(self):
        p = EVIDENCE_PACKET / "2023 Hyundai Elantra Weld Points Breadcrumb.txt"
        result = classify_intake_file(p)
        ev = build_file_evidence(result)
        # Weld Points breadcrumb should be detected
        assert ev["breadcrumb_evidence"]["breadcrumbs_found"] is True

    def test_breadcrumb_evidence_from_hyundai_procedure_fixture(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        ev = build_file_evidence(result)
        # This file has "Removal and Replacement" breadcrumb
        assert ev["breadcrumb_evidence"]["breadcrumbs_found"] is True


# ── Role evidence ─────────────────────────────────────────────────────────────

class TestRoleEvidence:
    def test_role_evidence_includes_primary_role(self):
        f = _make_file(document_role="repair_procedure")
        ev = build_file_evidence(f)
        assert ev["role_evidence"]["primary_role"] == "repair_procedure"

    def test_role_evidence_includes_supporting_roles(self):
        f = _make_file(
            document_role="repair_procedure",
            supporting_roles=["welding", "corrosion_protection"],
        )
        ev = build_file_evidence(f)
        assert "welding" in ev["role_evidence"]["supporting_roles"]
        assert "corrosion_protection" in ev["role_evidence"]["supporting_roles"]

    def test_role_scores_included(self):
        f = _make_file(
            document_role="repair_procedure",
            role_scores={"repair_procedure": 1.0, "welding": 0.45},
        )
        ev = build_file_evidence(f)
        assert ev["role_evidence"]["role_scores"]["repair_procedure"] == 1.0
        assert ev["role_evidence"]["role_scores"]["welding"] == 0.45

    def test_confidence_in_role_evidence(self):
        f = _make_file(confidence=0.72)
        ev = build_file_evidence(f)
        assert ev["role_evidence"]["confidence"] == pytest.approx(0.72)

    def test_confidence_explanation_is_string(self):
        f = _make_file(confidence=0.72, document_role="repair_procedure", detected_oem="Toyota")
        ev = build_file_evidence(f)
        assert isinstance(ev["role_evidence"]["confidence_explanation"], str)
        assert len(ev["role_evidence"]["confidence_explanation"]) > 10

    def test_phrase_evidence_separated_from_breadcrumb(self):
        f = _make_file(
            role_evidence=["removal and replacement", "[bc] weld points", "spot weld"],
        )
        ev = build_file_evidence(f)
        phrases = ev["role_evidence"]["role_evidence_phrases"]
        bc = ev["role_evidence"]["role_evidence_breadcrumbs"]
        assert "removal and replacement" in phrases
        assert "spot weld" in phrases
        assert "[bc] weld points" in bc
        assert "[bc] weld points" not in phrases


# ── summarize_role_coverage ───────────────────────────────────────────────────

class TestSummarizeRoleCoverage:
    def test_returns_dict(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = summarize_role_coverage(manifest)
        assert isinstance(result, dict)

    def test_required_keys(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = summarize_role_coverage(manifest)
        for key in (
            "roles_found", "roles_missing", "found_from_primary_role",
            "found_from_supporting_role_only", "coverage_detail", "coverage_note",
        ):
            assert key in result, f"Missing key: {key}"

    def test_toyota_repair_procedure_found(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = summarize_role_coverage(manifest)
        assert "repair_procedure" in result["roles_found"]

    def test_coverage_detail_has_all_tracked_roles(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = summarize_role_coverage(manifest)
        all_roles = [
            "repair_procedure", "sectioning", "welding", "corrosion_protection",
            "materials", "dimensions", "calibration", "precautions",
        ]
        for role in all_roles:
            assert role in result["coverage_detail"]

    def test_coverage_detail_has_found_and_source(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = summarize_role_coverage(manifest)
        for role, detail in result["coverage_detail"].items():
            assert "found" in detail
            assert "source" in detail

    def test_supporting_roles_count_as_found(self):
        # Create a manifest where repair_procedure is primary and welding is supporting
        f = _make_file(
            file_id="file_a",
            filename="procedure.txt",
            document_role="repair_procedure",
            supporting_roles=["welding", "corrosion_protection"],
            role_scores={"repair_procedure": 1.0, "welding": 0.45, "corrosion_protection": 0.35},
            confidence=0.65,
        )
        manifest = IntakeManifest(
            intake_id="test",
            files=[f],
            detected_packet=IntakePacket(
                detected_roles=["repair_procedure", "welding", "corrosion_protection"],
                file_count=1,
            ),
        )
        result = summarize_role_coverage(manifest)
        assert "welding" in result["roles_found"]
        assert "corrosion_protection" in result["roles_found"]
        assert "welding" not in result["roles_missing"]
        assert "corrosion_protection" not in result["roles_missing"]

    def test_supporting_role_source_labelled_correctly(self):
        f = _make_file(
            file_id="file_a",
            filename="procedure.txt",
            document_role="repair_procedure",
            supporting_roles=["welding"],
            confidence=0.65,
        )
        manifest = IntakeManifest(
            intake_id="test",
            files=[f],
            detected_packet=IntakePacket(detected_roles=["repair_procedure"], file_count=1),
        )
        result = summarize_role_coverage(manifest)
        # welding found from supporting only
        assert result["coverage_detail"]["welding"]["found"] is True
        assert result["coverage_detail"]["welding"]["source"] == "supporting_role"
        assert "welding" in result["found_from_supporting_role_only"]

    def test_primary_role_source_labelled_correctly(self):
        f = _make_file(
            file_id="file_a",
            filename="welding.txt",
            document_role="welding",
            confidence=0.65,
        )
        manifest = IntakeManifest(
            intake_id="test",
            files=[f],
            detected_packet=IntakePacket(detected_roles=["welding"], file_count=1),
        )
        result = summarize_role_coverage(manifest)
        assert result["coverage_detail"]["welding"]["source"] == "primary_role"
        assert "welding" not in result["found_from_supporting_role_only"]

    def test_error_files_excluded_from_coverage(self):
        f = _make_file(
            file_id="file_a",
            filename="bad.txt",
            document_role="unknown",
            supporting_roles=["welding"],
            errors=["File could not be read"],
            confidence=0.0,
        )
        manifest = IntakeManifest(
            intake_id="test",
            files=[f],
            detected_packet=IntakePacket(detected_roles=[], file_count=1),
        )
        result = summarize_role_coverage(manifest)
        # Error files should not contribute to coverage
        assert "welding" not in result["roles_found"]

    def test_missing_roles_exclude_supported_roles(self):
        # A file where repair_procedure is primary and welding is supporting
        # → welding should NOT appear in missing roles
        f = _make_file(
            file_id="file_a",
            filename="procedure.txt",
            document_role="repair_procedure",
            supporting_roles=["welding"],
            confidence=0.65,
        )
        manifest = IntakeManifest(
            intake_id="test",
            files=[f],
            detected_packet=IntakePacket(
                detected_roles=["repair_procedure", "welding"],
                file_count=1,
            ),
        )
        result = summarize_role_coverage(manifest)
        assert "welding" not in result["roles_missing"]


# ── Role coverage in classify_intake_packet ───────────────────────────────────

class TestPacketRoleCoverageIncludesSupporting:
    def test_detected_roles_includes_supporting_roles(self):
        # A file that has repair_procedure primary and welding/corrosion supporting
        p = EVIDENCE_PACKET / "2023 Hyundai Elantra Quarter Panel Procedure with Welding and Corrosion.txt"
        manifest = classify_intake_packet([p])
        detected = set(manifest.detected_packet.detected_roles)
        # repair_procedure must be detected (primary)
        assert "repair_procedure" in detected
        # welding and/or corrosion_protection should be detected via supporting roles
        assert "welding" in detected or "corrosion_protection" in detected

    def test_missing_roles_reduced_by_supporting_roles(self):
        p = EVIDENCE_PACKET / "2023 Hyundai Elantra Quarter Panel Procedure with Welding and Corrosion.txt"
        manifest = classify_intake_packet([p])
        # If welding is in supporting_roles, it should not be in missing_roles
        file_supporting = set()
        for f in manifest.files:
            file_supporting.update(f.supporting_roles)
        for role in file_supporting:
            if role in manifest.detected_packet.detected_roles:
                assert role not in manifest.missing_roles

    def test_evidence_packet_packet_coverage(self):
        paths = list(EVIDENCE_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        detected = set(manifest.detected_packet.detected_roles)
        # The evidence packet has repair procedure, welding, and corrosion files
        assert "repair_procedure" in detected


# ── explain_file_classification ───────────────────────────────────────────────

class TestExplainFileClassification:
    def test_returns_list(self):
        f = _make_file()
        result = explain_file_classification(f)
        assert isinstance(result, list)

    def test_returns_non_empty_list(self):
        f = _make_file(
            document_role="repair_procedure",
            detected_oem="Toyota",
            confidence=0.7,
        )
        result = explain_file_classification(f)
        assert len(result) >= 1

    def test_all_items_are_strings(self):
        f = _make_file(
            document_role="repair_procedure",
            detected_oem="Hyundai",
            supporting_roles=["welding"],
            confidence=0.65,
        )
        result = explain_file_classification(f)
        for item in result:
            assert isinstance(item, str)
            assert len(item) > 5

    def test_mentions_oem_when_detected(self):
        f = _make_file(detected_oem="Toyota", document_role="repair_procedure", confidence=0.7)
        result = explain_file_classification(f)
        joined = " ".join(result)
        assert "Toyota" in joined

    def test_mentions_unknown_when_no_oem(self):
        f = _make_file(detected_oem=None, document_role="unknown", confidence=0.1)
        result = explain_file_classification(f)
        joined = " ".join(result).lower()
        assert "no oem" in joined or "not detected" in joined or "unknown" in joined

    def test_mentions_primary_role(self):
        f = _make_file(
            document_role="welding",
            role_scores={"welding": 1.0},
            confidence=0.6,
        )
        result = explain_file_classification(f)
        joined = " ".join(result)
        assert "welding" in joined

    def test_mentions_supporting_roles_when_present(self):
        f = _make_file(
            document_role="repair_procedure",
            supporting_roles=["welding", "corrosion_protection"],
            confidence=0.65,
        )
        result = explain_file_classification(f)
        joined = " ".join(result)
        assert "welding" in joined
        assert "corrosion_protection" in joined

    def test_mentions_confidence(self):
        f = _make_file(confidence=0.72, document_role="repair_procedure")
        result = explain_file_classification(f)
        joined = " ".join(result)
        assert "%" in joined  # confidence displayed as percentage

    def test_mentions_breadcrumb_evidence(self):
        f = _make_file(
            document_role="welding",
            role_evidence=["[bc] weld points"],
            confidence=0.6,
        )
        result = explain_file_classification(f)
        joined = " ".join(result).lower()
        assert "breadcrumb" in joined

    def test_unknown_role_explanation(self):
        f = _make_file(document_role="unknown", confidence=0.1)
        result = explain_file_classification(f)
        joined = " ".join(result).lower()
        assert "unknown" in joined or "could not" in joined

    def test_classify_file_explain_for_real_fixture(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        intake_file = classify_intake_file(p)
        result = explain_file_classification(intake_file)
        assert isinstance(result, list)
        assert len(result) > 0
        joined = " ".join(result)
        assert "repair_procedure" in joined or "Hyundai" in joined


# ── diagnostics_for_file ──────────────────────────────────────────────────────

class TestDiagnosticsForFile:
    def test_sparse_text_code_for_empty_role_scores(self):
        f = _make_file(role_scores={}, role_evidence=[], warnings=[])
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_SPARSE_TEXT_EXTRACTION in codes

    def test_sparse_text_code_for_pdf_minimal_warning(self):
        f = _make_file(
            extension=".pdf",
            warnings=["PDF text extraction yielded minimal content."],
            role_scores={},
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_SPARSE_TEXT_EXTRACTION in codes

    def test_role_score_below_threshold_for_unknown_role(self):
        f = _make_file(document_role="unknown", role_scores={}, confidence=0.0)
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_ROLE_SCORE_BELOW_THRESHOLD in codes

    def test_role_coverage_from_supporting_code_when_supporting_roles(self):
        f = _make_file(
            document_role="repair_procedure",
            supporting_roles=["welding"],
            confidence=0.65,
            role_scores={"repair_procedure": 1.0, "welding": 0.4},
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_ROLE_COVERAGE_FROM_SUPPORTING in codes

    def test_breadcrumb_evidence_code_when_bc_in_evidence(self):
        f = _make_file(
            document_role="welding",
            role_evidence=["[bc] weld points"],
            confidence=0.6,
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_BREADCRUMB_EVIDENCE_FOUND in codes

    def test_filename_only_metadata_code_when_no_role_scores(self):
        f = _make_file(
            detected_oem="Toyota",
            document_role="unknown",
            role_scores={},
            confidence=0.0,
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_FILENAME_ONLY_METADATA in codes

    def test_error_file_returns_file_read_error_code(self):
        f = _make_file(errors=["Could not read file: no such file"], confidence=0.0)
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert "FILE_READ_ERROR" in codes

    def test_all_diagnostics_have_code_message(self):
        f = _make_file(document_role="unknown", role_scores={}, confidence=0.0)
        ev = build_file_evidence(f)
        for d in ev["diagnostics_for_file"]:
            assert "code" in d
            assert "message" in d
            assert isinstance(d["code"], str)
            assert isinstance(d["message"], str)

    def test_no_breadcrumb_code_when_no_breadcrumbs(self):
        f = _make_file(
            document_role="repair_procedure",
            role_evidence=["removal and replacement"],
            confidence=0.6,
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_BREADCRUMB_EVIDENCE_FOUND not in codes

    def test_sparse_fixture_triggers_sparse_text(self):
        p = EVIDENCE_PACKET / "sparse_document.txt"
        intake_file = classify_intake_file(p)
        ev = build_file_evidence(intake_file)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        # sparse document should trigger some kind of low-signal diagnostic
        low_signal_codes = {DIAG_SPARSE_TEXT_EXTRACTION, DIAG_ROLE_SCORE_BELOW_THRESHOLD}
        assert bool(low_signal_codes & set(codes)), (
            f"Expected low-signal diagnostic, got codes: {codes}"
        )


# ── build_intake_evidence_payload ─────────────────────────────────────────────

class TestBuildIntakeEvidencePayload:
    def test_returns_dict(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert isinstance(result, dict)

    def test_required_keys(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        for key in ("schema_name", "schema_version", "intake_id", "file_evidence",
                    "role_coverage", "advisory"):
            assert key in result, f"Missing key: {key}"

    def test_schema_name_correct(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert result["schema_name"] == "repairgraph.intake_evidence"

    def test_file_evidence_count_matches_manifest(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert len(result["file_evidence"]) == len(manifest.files)

    def test_role_coverage_included(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert isinstance(result["role_coverage"], dict)
        assert "roles_found" in result["role_coverage"]

    def test_intake_id_matches_manifest(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert result["intake_id"] == manifest.intake_id

    def test_advisory_is_non_empty_string(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        result = build_intake_evidence_payload(manifest)
        assert isinstance(result["advisory"], str)
        assert len(result["advisory"]) > 10

    def test_empty_manifest_returns_empty_file_evidence(self):
        manifest = IntakeManifest(intake_id="test_empty")
        result = build_intake_evidence_payload(manifest)
        assert result["file_evidence"] == []

    def test_deterministic_for_same_manifest(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        r1 = build_intake_evidence_payload(manifest)
        r2 = build_intake_evidence_payload(manifest)
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ── API endpoint /internal/intake/evidence ────────────────────────────────────

class TestEvidenceEndpoint:
    def test_returns_200(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        assert response.status_code == 200

    def test_returns_json(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        assert "application/json" in response.headers["content-type"]

    def test_response_has_schema_name(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        assert data.get("schema_name") == "repairgraph.intake_evidence"

    def test_response_has_file_evidence(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        assert "file_evidence" in data
        assert isinstance(data["file_evidence"], list)
        assert len(data["file_evidence"]) > 0

    def test_response_has_role_coverage(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        assert "role_coverage" in data
        assert "roles_found" in data["role_coverage"]

    def test_response_has_advisory(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        assert "advisory" in data
        assert isinstance(data["advisory"], str)

    def test_no_files_returns_422(self):
        response = client.post("/internal/intake/evidence", files=[])
        assert response.status_code == 422

    def test_evidence_packet_returns_200(self):
        response = client.post("/internal/intake/evidence", files=_evidence_packet_files())
        assert response.status_code == 200

    def test_evidence_payload_is_valid_json(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        # Must parse without error
        data = response.json()
        assert data is not None

    def test_file_evidence_items_have_required_keys(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        for item in data["file_evidence"]:
            for key in ("file_id", "filename", "filename_evidence",
                        "text_evidence", "role_evidence", "classification_explanation"):
                assert key in item, f"Missing key {key} in file_evidence item"

    def test_toyota_repair_procedure_in_role_coverage(self):
        response = client.post("/internal/intake/evidence", files=_toyota_files())
        data = response.json()
        coverage = data["role_coverage"]
        assert "repair_procedure" in coverage["roles_found"]


# ── Report contains Evidence Inspector ───────────────────────────────────────

class TestReportEvidenceInspector:
    def test_report_contains_evidence_inspector(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Evidence Inspector" in response.text

    def test_report_contains_evidence_for_each_file(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Classification Explanation" in response.text

    def test_report_role_coverage_uses_corrected_logic(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        # Should show role coverage with supporting role logic
        assert "role-found" in response.text or "role-missing" in response.text

    def test_report_no_external_cdn(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert 'src="http' not in response.text
        assert "cdn.jsdelivr" not in response.text


# ── Upload page contains evidence display ─────────────────────────────────────

class TestUploadPageEvidenceDisplay:
    def test_upload_page_references_evidence_inspector(self):
        response = client.get("/internal/intake")
        assert "evidence" in response.text.lower() or "Evidence" in response.text

    def test_upload_page_has_supporting_role_css(self):
        response = client.get("/internal/intake")
        assert "role-found-supporting" in response.text

    def test_upload_page_has_text_quality_css(self):
        response = client.get("/internal/intake")
        assert "text-quality" in response.text

    def test_upload_page_has_render_evidence(self):
        response = client.get("/internal/intake")
        assert "renderEvidenceSection" in response.text or "Evidence Inspector" in response.text


# ── Low-confidence file explanation ──────────────────────────────────────────

class TestLowConfidenceExplanation:
    def test_low_confidence_file_has_explanation(self):
        f = _make_file(confidence=0.1, document_role="unknown", role_scores={})
        ev = build_file_evidence(f)
        explanation = ev["classification_explanation"]
        assert isinstance(explanation, list)
        assert len(explanation) > 0

    def test_unknown_role_mentioned_in_diagnostics(self):
        f = _make_file(document_role="unknown", confidence=0.0, role_scores={})
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_ROLE_SCORE_BELOW_THRESHOLD in codes

    def test_low_confidence_threshold_produces_threshold_code(self):
        f = _make_file(
            document_role="repair_procedure",
            confidence=0.15,
            detected_oem=None,
        )
        ev = build_file_evidence(f)
        codes = [d["code"] for d in ev["diagnostics_for_file"]]
        assert DIAG_ROLE_SCORE_BELOW_THRESHOLD in codes

    def test_unknown_content_fixture_low_confidence(self):
        p = EVIDENCE_PACKET / "unknown_content_no_oem.txt"
        intake_file = classify_intake_file(p)
        # Should be low confidence or unknown role
        assert intake_file.confidence < 0.5 or intake_file.document_role == "unknown"
        ev = build_file_evidence(intake_file)
        assert isinstance(ev["diagnostics_for_file"], list)


# ── Regression: existing tests still pass ────────────────────────────────────

class TestRegressionExistingFunctionality:
    def test_classify_intake_file_still_works(self):
        p = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(p)
        assert result.document_role == "repair_procedure"
        assert result.detected_oem == "Toyota"

    def test_classify_intake_packet_still_returns_manifest(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.intake_id.startswith("intake_")
        assert manifest.readiness in ("ready", "partial", "incomplete", "unprocessable")

    def test_hyundai_packet_roles_still_detected(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        detected = set(manifest.detected_packet.detected_roles)
        assert "repair_procedure" in detected
        assert "welding" in detected
        assert "corrosion_protection" in detected

    def test_classify_endpoint_still_200(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        assert response.status_code == 200

    def test_report_endpoint_still_200(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert response.status_code == 200

    def test_upload_page_still_200(self):
        response = client.get("/internal/intake")
        assert response.status_code == 200
