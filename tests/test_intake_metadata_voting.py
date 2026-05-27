"""
Tests for generalised OEM metadata detection hardening.

Covers:
- Filename metadata extraction (separator normalization, OEM/model/year/operation)
- Isolation penalty for weak OEM mentions in long noisy text
- Filename-vs-text metadata merge and conflict detection
- Packet-level voting with filename evidence
- Synthetic Subaru-like noisy packet (regression for real-world false-positive case)
- Existing Toyota/Ford fixtures unaffected
"""
from __future__ import annotations

from pathlib import Path

import pytest

from repairgraph.intake.classify import (
    _extract_filename_metadata,
    _score_oem,
    classify_intake_file,
    classify_intake_packet,
    detect_oem_metadata,
)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
FORD_PACKET = FIXTURES / "ford_packet"
SUBARU_PACKET = FIXTURES / "subaru_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


# ── _score_oem (isolation penalty) ───────────────────────────────────────────

class TestScoreOemIsolationPenalty:
    def test_single_hit_in_long_text_penalized(self):
        long_noise = "x " * 600  # > 1000 chars
        text = long_noise + " volkswagen " + long_noise
        lower = text.lower()
        scores = _score_oem(lower, len(lower))
        assert "Volkswagen" in scores
        # Penalized: 1 hit in > 1000 char text → score = 0.4
        assert scores["Volkswagen"] < 1.0

    def test_two_hits_in_long_text_penalized(self):
        long_noise = "a " * 600
        text = long_noise + " volkswagen " + long_noise + " vw " + long_noise
        lower = text.lower()
        scores = _score_oem(lower, len(lower))
        assert scores.get("Volkswagen", 0) < 2.0  # penalized

    def test_three_hits_in_long_text_not_penalized(self):
        # 3 hits = genuine signal even in long text
        long_noise = "a " * 400
        text = long_noise + " subaru subaru subaru " + long_noise
        lower = text.lower()
        scores = _score_oem(lower, len(lower))
        assert scores.get("Subaru", 0) == 3.0  # no penalty

    def test_single_hit_in_short_text_not_penalized(self):
        # Short text (< 1000 chars): no isolation penalty
        text = "honda accord repair procedure"
        lower = text.lower()
        scores = _score_oem(lower, len(lower))
        assert scores.get("Honda", 0) == 1.0  # full score

    def test_weak_oem_does_not_beat_strong_oem(self):
        # Subaru appears 5x, VW appears once in long text
        long_noise = "b " * 300
        text = (
            long_noise
            + " subaru subaru subaru subaru subaru "
            + long_noise
            + " volkswagen "
            + long_noise
        )
        lower = text.lower()
        scores = _score_oem(lower, len(lower))
        assert scores.get("Subaru", 0) > scores.get("Volkswagen", 0)


# ── _extract_filename_metadata ────────────────────────────────────────────────

class TestExtractFilenameMetadata:
    def test_year_extracted_from_leading_year(self):
        m = _extract_filename_metadata("2024 Subaru Outback Quarter Panel Replacement")
        assert m["year"] == 2024

    def test_year_extracted_from_trailing_year(self):
        m = _extract_filename_metadata("Subaru_Outback_2024_rear_side_outer_panel")
        assert m["year"] == 2024

    def test_oem_extracted_from_natural_name(self):
        m = _extract_filename_metadata("2024 Subaru Outback Quarter Panel Replacement")
        assert m["oem"] == "Subaru"

    def test_oem_extracted_with_underscores(self):
        m = _extract_filename_metadata("Subaru_Outback_2024_rear_side_outer_panel")
        assert m["oem"] == "Subaru"

    def test_oem_extracted_ford_with_hyphens(self):
        m = _extract_filename_metadata("2022-Ford-F-150-Bed-Side-Panel-Repair-Procedure")
        assert m["oem"] == "Ford"

    def test_oem_extracted_toyota(self):
        m = _extract_filename_metadata("2023 Toyota Camry Welding Specs")
        assert m["oem"] == "Toyota"

    def test_model_extracted_outback(self):
        m = _extract_filename_metadata("2024 Subaru Outback Quarter Panel Replacement")
        assert m["model"] == "Outback"

    def test_model_extracted_camry(self):
        m = _extract_filename_metadata("2023 Toyota Camry Welding Specs")
        assert m["model"] == "Camry"

    def test_model_extracted_f150(self):
        m = _extract_filename_metadata("2022 Ford F-150 Bed Side Panel Repair Procedure")
        assert m["model"] == "F-150"

    def test_operation_detected_quarter_panel(self):
        m = _extract_filename_metadata("2024 Subaru Outback Quarter Panel Replacement")
        assert m["operation"] == "quarter_panel_replacement"

    def test_operation_detected_bed_side(self):
        m = _extract_filename_metadata("2022 Ford F-150 Bed Side Panel Repair Procedure")
        assert m["operation"] is not None

    def test_no_oem_in_plain_filename(self):
        m = _extract_filename_metadata("camry_repair_procedure")
        # "camry" is a model, not an OEM — OEM should be None
        assert m["oem"] is None

    def test_model_found_without_oem(self):
        m = _extract_filename_metadata("camry_repair_procedure")
        assert m["model"] == "Camry"

    def test_separator_normalization_alldata_style(self):
        # Parentheses, brackets, mixed separators
        m = _extract_filename_metadata(
            "2024 Subaru Outback Quarter Panel Replacement - ALLDATA Collision"
        )
        assert m["oem"] == "Subaru"
        assert m["year"] == 2024

    def test_no_year_in_filename(self):
        m = _extract_filename_metadata("subaru_outback_corrosion_protection")
        assert m["year"] is None

    def test_year_out_of_range_ignored(self):
        m = _extract_filename_metadata("1234 Subaru Outback Panel 9999")
        assert m["year"] is None

    def test_all_keys_present(self):
        m = _extract_filename_metadata("test_file")
        for key in ("oem", "model", "year", "operation"):
            assert key in m

    def test_deterministic(self):
        stem = "2024 Subaru Outback Quarter Panel Replacement"
        assert _extract_filename_metadata(stem) == _extract_filename_metadata(stem)


# ── detect_oem_metadata (canonical model names) ───────────────────────────────

class TestDetectOemMetadataModelNames:
    def test_toyota_camry_canonical(self):
        result = detect_oem_metadata("Toyota Camry 2023 repair procedure")
        assert result["model"] == "Camry"

    def test_subaru_outback_canonical(self):
        result = detect_oem_metadata("Subaru Outback 2024 quarter panel replacement")
        assert result["model"] == "Outback"

    def test_ford_f150_canonical(self):
        result = detect_oem_metadata("Ford F-150 2022 repair procedure")
        assert result["model"] == "F-150"

    def test_honda_crv_canonical(self):
        result = detect_oem_metadata("Honda CR-V 2025 repair body panel")
        assert result["model"] == "CR-V"

    def test_model_is_string_not_pattern(self):
        result = detect_oem_metadata("Toyota Camry 2023 quarter panel")
        assert result["model"] is None or not result["model"].startswith(r"\b")


# ── classify_intake_file (filename + text merge) ──────────────────────────────

class TestClassifyIntakeFileFilenameEvidence:
    def test_filename_oem_detected_when_text_is_empty(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        f.write_text("This document has no OEM keywords.", encoding="utf-8")
        result = classify_intake_file(f)
        assert result.detected_oem == "Subaru"

    def test_filename_year_detected_when_text_has_none(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        f.write_text("This document has no year mention.", encoding="utf-8")
        result = classify_intake_file(f)
        assert result.detected_year == 2024

    def test_filename_model_detected(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        f.write_text("Body panel replacement procedure removal installation step 1.", encoding="utf-8")
        result = classify_intake_file(f)
        assert result.detected_model == "Outback"

    def test_filename_and_text_agree_boosts_confidence(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        f.write_text(
            "Subaru Outback 2024 rear quarter panel replacement procedure. "
            "Subaru specifies removal of the Outback rear panel per Subaru weld map.",
            encoding="utf-8",
        )
        result = classify_intake_file(f)
        assert result.detected_oem == "Subaru"
        assert result.confidence > 0.50

    def test_filename_wins_over_isolated_text_oem(self, tmp_path):
        # Filename says Subaru; text has one isolated Volkswagen mention in long content
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        padding = "repair body panel removal installation step " * 60  # >1000 chars
        content = padding + " volkswagen " + padding
        f.write_text(content, encoding="utf-8")
        result = classify_intake_file(f)
        assert result.detected_oem == "Subaru"

    def test_conflict_warning_generated(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        padding = "body panel removal installation " * 60
        content = padding + " volkswagen " + padding
        f.write_text(content, encoding="utf-8")
        result = classify_intake_file(f)
        conflict_warns = [w for w in result.warnings if "METADATA_CONFLICT" in w]
        assert conflict_warns

    def test_no_false_conflict_when_oems_agree(self, tmp_path):
        f = tmp_path / "2024 Subaru Outback Procedure.txt"
        f.write_text(
            "Subaru Outback 2024. Subaru Subaru Subaru repair procedure removal.",
            encoding="utf-8",
        )
        result = classify_intake_file(f)
        conflict_warns = [w for w in result.warnings if "METADATA_CONFLICT" in w]
        assert not conflict_warns


# ── classify_intake_packet (filename voting + new diagnostics) ────────────────

class TestClassifyIntakePacketFilenameVoting:
    def test_subaru_packet_detected(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Subaru"

    def test_subaru_packet_model_detected(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_model == "Outback"

    def test_subaru_packet_year_detected(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_year == 2024

    def test_subaru_packet_volkswagen_does_not_win(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem != "Volkswagen"

    def test_subaru_packet_readiness(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.readiness in ("ready", "partial")

    def test_subaru_packet_oem_confidence_reasonable(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.oem_confidence >= 0.40

    def test_filename_text_disagreement_diagnostic_emitted(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        # At least one file has VW in text but Subaru in filename
        codes = [d.code for d in manifest.diagnostics]
        assert "FILENAME_TEXT_DISAGREEMENT" in codes or "OEM_DETECTED_BY_FILENAME" in codes

    def test_oem_detected_by_filename_diagnostic(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        codes = [d.code for d in manifest.diagnostics]
        assert "OEM_DETECTED_BY_FILENAME" in codes

    def test_toyota_packet_still_detects_toyota(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Toyota"

    def test_toyota_packet_still_ready(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.readiness in ("ready", "partial")

    def test_ford_packet_still_detects_ford(self):
        paths = list(FORD_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Ford"

    def test_oem_conflict_diagnostic_for_mixed_packet(self, tmp_path):
        # Two files disagreeing on OEM at text level
        f1 = tmp_path / "toyota_procedure.txt"
        f1.write_text(
            "Toyota Camry 2023 Toyota repair procedure removal installation step 1.",
            encoding="utf-8",
        )
        f2 = tmp_path / "honda_procedure.txt"
        f2.write_text(
            "Honda Accord 2025 Honda repair procedure removal installation step 1.",
            encoding="utf-8",
        )
        manifest = classify_intake_packet([f1, f2])
        codes = [d.code for d in manifest.diagnostics]
        assert "OEM_CONFLICT" in codes

    def test_weak_metadata_confidence_diagnostic(self, tmp_path):
        # Very sparse OEM signal: 1 mention in long noisy text
        f = tmp_path / "ambiguous_file.txt"
        noise = "repair body panel removal installation step " * 100
        content = noise + " subaru " + noise
        f.write_text(content, encoding="utf-8")
        manifest = classify_intake_packet([f])
        if manifest.detected_packet.oem_confidence < 0.40:
            codes = [d.code for d in manifest.diagnostics]
            assert "WEAK_METADATA_CONFIDENCE" in codes

    def test_year_from_filename_takes_priority(self, tmp_path):
        # Filename says 2024; text only has 2020 (e.g. in copyright notice)
        f = tmp_path / "2024_Subaru_Outback_procedure.txt"
        f.write_text(
            "This document is copyright 2020. Subaru repair procedure.",
            encoding="utf-8",
        )
        manifest = classify_intake_packet([f])
        assert manifest.detected_packet.detected_year == 2024


# ── Conflict fixture ──────────────────────────────────────────────────────────

class TestFilenameTextConflict:
    def test_conflict_fixture_generates_disagreement_diagnostic(self):
        # honda_accord_procedure.txt has Toyota content despite Honda filename
        path = MIXED_PACKET / "honda_accord_procedure.txt"
        manifest = classify_intake_packet([path])
        codes = [d.code for d in manifest.diagnostics]
        assert "FILENAME_TEXT_DISAGREEMENT" in codes

    def test_conflict_fixture_file_has_warning(self):
        path = MIXED_PACKET / "honda_accord_procedure.txt"
        result = classify_intake_file(path)
        conflict_warns = [w for w in result.warnings if "METADATA_CONFLICT" in w]
        assert conflict_warns

    def test_conflict_fixture_filename_oem_wins(self):
        # File is named "honda_accord_procedure.txt" → filename says Honda
        # Text is all Toyota → text says Toyota
        path = MIXED_PACKET / "honda_accord_procedure.txt"
        result = classify_intake_file(path)
        # Filename has no "honda" in stem "honda_accord_procedure"...
        # Actually: stem = "honda_accord_procedure" → OEM pattern r"\bhonda\b" matches
        assert result.detected_oem == "Honda"


# ── Regression: existing classify tests still pass ───────────────────────────

class TestExistingClassifyRegression:
    def test_detect_oem_toyota_short_text(self):
        result = detect_oem_metadata("TOYOTA MOTOR CORPORATION 2023 TOYOTA CAMRY repair procedure")
        assert result["oem"] == "Toyota"

    def test_detect_oem_honda_short_text(self):
        result = detect_oem_metadata("Honda Accord 2025 repair body panel replacement procedure")
        assert result["oem"] == "Honda"

    def test_detect_oem_ford_short_text(self):
        result = detect_oem_metadata("FORD MOTOR COMPANY 2022 FORD F-150 repair procedure")
        assert result["oem"] == "Ford"

    def test_confidence_positive_for_oem_text(self):
        result = detect_oem_metadata("Toyota Motor Corporation repair manual")
        assert result["confidence"] > 0.0

    def test_toyota_file_classification(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.detected_oem == "Toyota"
        assert result.confidence > 0.0

    def test_ford_file_oem(self):
        src = FORD_PACKET / "f150_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.detected_oem == "Ford"
        assert result.confidence > 0.0

    def test_toyota_packet_year(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.detected_year == 2023
