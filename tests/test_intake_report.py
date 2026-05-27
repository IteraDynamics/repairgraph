"""
Tests for repairgraph.intake.report.

Verifies HTML report generation, content requirements, advisory language,
self-contained structure, and determinism.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from repairgraph.intake.classify import classify_intake_packet
from repairgraph.intake.report import build_intake_html_report, build_intake_summary_cards
from repairgraph.intake.schema import IntakeManifest, IntakePacket

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
FORD_PACKET = FIXTURES / "ford_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


def _toyota_manifest() -> IntakeManifest:
    return classify_intake_packet(list(TOYOTA_PACKET.iterdir()))


def _empty_manifest() -> IntakeManifest:
    return IntakeManifest(intake_id="test_empty")


# ── build_intake_summary_cards ────────────────────────────────────────────────

class TestBuildIntakeSummaryCards:
    def test_returns_list(self):
        cards = build_intake_summary_cards(_toyota_manifest())
        assert isinstance(cards, list)
        assert len(cards) > 0

    def test_cards_have_required_keys(self):
        cards = build_intake_summary_cards(_toyota_manifest())
        for card in cards:
            assert "value" in card
            assert "label" in card
            assert "accent" in card

    def test_card_values_are_strings(self):
        cards = build_intake_summary_cards(_toyota_manifest())
        for card in cards:
            assert isinstance(card["value"], str)
            assert isinstance(card["label"], str)

    def test_files_card_present(self):
        cards = build_intake_summary_cards(_toyota_manifest())
        labels = [c["label"].lower() for c in cards]
        assert any("file" in lbl for lbl in labels)

    def test_errors_card_present(self):
        cards = build_intake_summary_cards(_toyota_manifest())
        labels = [c["label"].lower() for c in cards]
        assert any("error" in lbl for lbl in labels)

    def test_deterministic(self):
        manifest = _toyota_manifest()
        c1 = build_intake_summary_cards(manifest)
        c2 = build_intake_summary_cards(manifest)
        assert c1 == c2

    def test_empty_manifest_cards(self):
        cards = build_intake_summary_cards(_empty_manifest())
        assert isinstance(cards, list)


# ── build_intake_html_report ──────────────────────────────────────────────────

class TestBuildIntakeHtmlReport:
    def test_returns_string(self):
        html = build_intake_html_report(_toyota_manifest())
        assert isinstance(html, str)

    def test_valid_html_document(self):
        html = build_intake_html_report(_toyota_manifest())
        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_contains_advisory_banner(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "advisory-banner" in html
        assert "Advisory" in html

    def test_contains_advisory_language(self):
        html = build_intake_html_report(_toyota_manifest())
        text = html.lower()
        assert "advisory" in text
        assert "oem" in text

    def test_not_oem_distribution_platform(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "not an OEM document distribution platform" in html or \
               "not an oem document distribution platform" in html.lower()

    def test_contains_repairgraph_branding(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "RepairGraph" in html

    def test_contains_intake_summary_section(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Intake Summary" in html

    def test_contains_packet_metadata_section(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Detected Packet Metadata" in html or "Packet" in html

    def test_contains_role_coverage_section(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Role" in html

    def test_contains_file_classifications(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "File Classifications" in html or "Classifications" in html

    def test_contains_diagnostics_section(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Diagnostic" in html

    def test_contains_readiness_section(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Readiness" in html

    def test_toyota_oem_in_report(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Toyota" in html

    def test_ford_oem_in_report(self):
        manifest = classify_intake_packet(list(FORD_PACKET.iterdir()))
        html = build_intake_html_report(manifest)
        assert "Ford" in html

    def test_inline_css_present(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "<style>" in html

    def test_no_external_cdn(self):
        html = build_intake_html_report(_toyota_manifest())
        assert 'src="http' not in html
        assert "cdn.jsdelivr" not in html
        assert "unpkg.com" not in html

    def test_deterministic_same_manifest(self):
        manifest = _toyota_manifest()
        h1 = build_intake_html_report(manifest)
        h2 = build_intake_html_report(manifest)
        assert h1 == h2

    def test_empty_manifest_does_not_crash(self):
        html = build_intake_html_report(_empty_manifest())
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html

    def test_report_larger_than_threshold(self):
        html = build_intake_html_report(_toyota_manifest())
        assert len(html) > 3000

    def test_contains_missing_roles(self):
        html = build_intake_html_report(_empty_manifest())
        # Empty manifest has missing roles
        assert "Missing" in html or "missing" in html

    def test_contains_confidence_indicators(self):
        html = build_intake_html_report(_toyota_manifest())
        # Confidence shown as percentage
        assert "%" in html

    def test_contains_generated_by_footer(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "repairgraph.intake.report" in html

    def test_mixed_packet_handles_gracefully(self):
        manifest = classify_intake_packet(list(MIXED_PACKET.iterdir()))
        html = build_intake_html_report(manifest)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html

    def test_warnings_card_shows_in_summary(self):
        html = build_intake_html_report(_toyota_manifest())
        assert "Warning" in html
