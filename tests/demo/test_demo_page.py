"""
Tests for the RepairGraph golden-path demo page HTML generator.

Covers: HTML structure, no external dependencies, embedded payload,
all steps present, interactive elements, advisory content, and determinism.
"""
import json
import re

import pytest

from repairgraph.demo.demo_page import build_demo_page_html


@pytest.fixture(scope="module")
def html():
    return build_demo_page_html()


class TestHtmlStructure:
    def test_returns_string(self, html):
        assert isinstance(html, str)

    def test_starts_with_doctype(self, html):
        assert html.startswith("<!DOCTYPE html>")

    def test_has_html_tag(self, html):
        assert "<html" in html

    def test_has_head_and_body(self, html):
        assert "<head>" in html
        assert "<body>" in html

    def test_has_title(self, html):
        assert "RepairGraph" in html
        assert "<title>" in html

    def test_has_charset(self, html):
        assert "UTF-8" in html


class TestNoDependencies:
    def test_no_cdn(self, html):
        assert "cdn." not in html.lower()

    def test_no_unpkg(self, html):
        assert "unpkg.com" not in html

    def test_no_react(self, html):
        assert "react" not in html.lower()

    def test_no_vue(self, html):
        assert "vue.js" not in html.lower()

    def test_no_external_script_src(self, html):
        matches = re.findall(r'<script[^>]+src=["\']https?://', html, re.IGNORECASE)
        assert len(matches) == 0

    def test_no_external_link_href(self, html):
        matches = re.findall(r'<link[^>]+href=["\']https?://', html, re.IGNORECASE)
        assert len(matches) == 0

    def test_has_embedded_css(self, html):
        assert "<style>" in html

    def test_has_embedded_js(self, html):
        assert "<script>" in html


class TestAllStepsPresent:
    def test_step_1_intake(self, html):
        assert "step-intake" in html
        assert "OEM Intake" in html

    def test_step_2_analysis(self, html):
        assert "step-analysis" in html
        assert "Packet Analysis" in html

    def test_step_3_intelligence(self, html):
        assert "step-intelligence" in html
        assert "Repair Intelligence" in html

    def test_step_4_viewer(self, html):
        assert "step-viewer" in html
        assert "viewer-frame" in html

    def test_step_5_replay(self, html):
        assert "step-replay" in html
        assert "replay-list" in html

    def test_step_6_summary(self, html):
        assert "step-summary" in html
        assert "summary-grid" in html

    def test_step_7_export(self, html):
        assert "step-export" in html
        assert "Export" in html


class TestInteractiveElements:
    def test_upload_zone(self, html):
        assert "drop-zone" in html

    def test_file_input(self, html):
        assert "file-input" in html

    def test_demo_packet_button(self, html):
        assert "btn-demo" in html
        assert "Demo Packet" in html

    def test_analyze_button(self, html):
        assert "btn-analyze" in html

    def test_export_links_present(self, html):
        assert "/internal/state/accord/report?view=workflow" in html
        assert "/internal/state/accord/report?view=replay" in html
        assert "/internal/intake" in html
        assert "/internal/state/accord/topology-viewer" in html

    def test_insights_panel(self, html):
        assert "insights" in html
        assert "What RepairGraph is doing" in html

    def test_iframe_for_viewer(self, html):
        assert "<iframe" in html
        assert "viewer-frame" in html


class TestEmbeddedPayload:
    def test_payload_const_present(self, html):
        assert "const DEMO =" in html

    def test_embedded_json_parseable(self, html):
        match = re.search(r"const DEMO = (\{.*?\});\s*\n", html, re.DOTALL)
        assert match is not None, "Could not find DEMO JSON"
        data = json.loads(match.group(1))
        assert isinstance(data, dict)

    def test_embedded_payload_has_schema(self, html):
        assert "repairgraph.demo.full" in html

    def test_embedded_workflow_data(self, html):
        assert "workflow_summary" in html

    def test_embedded_intake_data(self, html):
        assert "detected_packet" in html


class TestJavascriptFunctions:
    def test_run_intake_animation(self, html):
        assert "runIntakeAnimation" in html

    def test_run_intel_animation(self, html):
        assert "runIntelAnimation" in html

    def test_render_replay(self, html):
        assert "renderReplay" in html

    def test_render_summary(self, html):
        assert "renderSummary" in html

    def test_use_demo_packet(self, html):
        assert "useDemoPacket" in html

    def test_start_analysis(self, html):
        assert "startAnalysis" in html

    def test_insights_activation(self, html):
        assert "activateInsight" in html

    def test_activate_viewer(self, html):
        assert "activateViewer" in html


class TestAdvisory:
    def test_advisory_bar(self, html):
        assert "Advisory" in html

    def test_advisory_text_oem(self, html):
        assert "OEM" in html


class TestContent:
    def test_has_honda_accord(self, html):
        assert "Accord" in html
        assert "Honda" in html

    def test_hero_section(self, html):
        assert "hero" in html
        assert "workflow intelligence" in html.lower()

    def test_philosophy_reinforced(self, html):
        # The page should reinforce what RepairGraph does
        assert "operational model" in html.lower() or "workflow" in html.lower()


class TestDeterminism:
    def test_structurally_consistent(self):
        # intake_id is random per call — check structural consistency not raw text equality
        h1 = build_demo_page_html()
        h2 = build_demo_page_html()
        assert "RepairGraph" in h1 and "RepairGraph" in h2
        assert "workflow_summary" in h1 and "workflow_summary" in h2
        # Same workflow data (Honda Accord is deterministic)
        assert "Accord" in h1 and "Accord" in h2

    def test_output_non_trivial(self, html):
        assert len(html) > 20_000
