"""
Tests for the topology viewer HTML generator.

Covers: HTML structure, embedded payload, SVG presence, CSS/JS inclusion,
self-contained output (no CDN/external refs), and export functionality.
"""
import json
import re

import pytest

from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
)
from repairgraph.viewer.topology_layout import VEHICLE_REGIONS
from repairgraph.viewer.topology_viewer import build_topology_viewer_html


@pytest.fixture(scope="module")
def initial():
    return build_accord_initial_state()


@pytest.fixture(scope="module")
def events(initial):
    return build_accord_demo_events(initial)


@pytest.fixture(scope="module")
def html_output(initial, events):
    return build_topology_viewer_html(initial, events)


class TestHtmlStructure:
    def test_returns_string(self, html_output):
        assert isinstance(html_output, str)

    def test_starts_with_doctype(self, html_output):
        assert html_output.startswith("<!DOCTYPE html>")

    def test_has_html_tag(self, html_output):
        assert "<html" in html_output

    def test_has_head_and_body(self, html_output):
        assert "<head>" in html_output
        assert "<body>" in html_output

    def test_has_title(self, html_output):
        assert "<title>" in html_output
        assert "RepairGraph" in html_output

    def test_has_charset_meta(self, html_output):
        assert 'charset="UTF-8"' in html_output or "charset=UTF-8" in html_output.lower()


class TestNoDependencies:
    def test_no_cdn_links(self, html_output):
        assert "cdn." not in html_output.lower()
        assert "unpkg.com" not in html_output
        assert "jsdelivr.net" not in html_output
        assert "cloudflare.com" not in html_output

    def test_no_react(self, html_output):
        assert "react" not in html_output.lower()

    def test_no_vue(self, html_output):
        assert "vue.js" not in html_output.lower()

    def test_no_external_script_src(self, html_output):
        # Inline scripts only — no src= pointing to http(s) URLs
        external_scripts = re.findall(r'<script[^>]+src=["\']https?://', html_output, re.IGNORECASE)
        assert len(external_scripts) == 0

    def test_no_external_link_href(self, html_output):
        external_links = re.findall(r'<link[^>]+href=["\']https?://', html_output, re.IGNORECASE)
        assert len(external_links) == 0

    def test_has_embedded_css(self, html_output):
        assert "<style>" in html_output

    def test_has_embedded_js(self, html_output):
        assert "<script>" in html_output


class TestSvgVehicle:
    def test_has_svg_element(self, html_output):
        assert "<svg" in html_output

    def test_all_regions_in_svg(self, html_output):
        for reg in VEHICLE_REGIONS:
            assert reg["id"] in html_output, f"Region {reg['id']} not found in SVG"

    def test_svg_has_viewbox(self, html_output):
        assert "viewBox" in html_output

    def test_regions_have_onclick(self, html_output):
        assert "onclick" in html_output
        assert "selectRegion" in html_output

    def test_regions_have_data_region_attr(self, html_output):
        assert "data-region=" in html_output


class TestEmbeddedPayload:
    def test_payload_const_present(self, html_output):
        assert "const PAYLOAD =" in html_output

    def test_embedded_json_is_valid(self, html_output):
        match = re.search(r"const PAYLOAD = (\{.*?\});\s*\n", html_output, re.DOTALL)
        assert match is not None, "Could not find PAYLOAD JSON"
        # Should parse without error
        data = json.loads(match.group(1))
        assert isinstance(data, dict)

    def test_embedded_payload_has_schema_name(self, html_output):
        assert "repairgraph.viewer.topology" in html_output

    def test_embedded_payload_has_session(self, html_output):
        assert "Honda" in html_output
        assert "Accord" in html_output

    def test_embedded_payload_has_replay_snapshots(self, html_output):
        assert "replay_snapshots" in html_output


class TestInteractiveElements:
    def test_has_timeline_panel(self, html_output):
        assert "timeline-panel" in html_output
        assert "timeline-track" in html_output

    def test_has_inspector_panel(self, html_output):
        assert "inspector" in html_output

    def test_has_filter_checkboxes(self, html_output):
        assert "filter-qa" in html_output
        assert "filter-blockers" in html_output
        assert "filter-completed" in html_output
        assert "filter-deps" in html_output

    def test_has_replay_controls(self, html_output):
        assert "btn-prev" in html_output
        assert "btn-next" in html_output
        assert "btn-latest" in html_output
        assert "timeline-range" in html_output

    def test_has_export_button(self, html_output):
        assert "export-btn" in html_output
        assert "exportViewer" in html_output

    def test_has_legend(self, html_output):
        assert "legend" in html_output.lower()

    def test_has_status_cards(self, html_output):
        assert "card-actions" in html_output
        assert "card-blockers" in html_output
        assert "card-qa" in html_output


class TestJavaScriptFunctions:
    def test_set_step_function(self, html_output):
        assert "function setStep" in html_output

    def test_select_region_function(self, html_output):
        assert "function selectRegion" in html_output

    def test_apply_region_map_function(self, html_output):
        assert "function applyRegionMap" in html_output

    def test_update_inspector_function(self, html_output):
        assert "function updateInspector" in html_output

    def test_build_timeline_function(self, html_output):
        assert "function buildTimeline" in html_output

    def test_export_function(self, html_output):
        assert "function exportViewer" in html_output

    def test_apply_filters_function(self, html_output):
        assert "function applyFilters" in html_output

    def test_keyboard_navigation(self, html_output):
        assert "ArrowLeft" in html_output
        assert "ArrowRight" in html_output


class TestDeterminism:
    def test_output_is_deterministic(self, initial, events):
        h1 = build_topology_viewer_html(initial, events)
        h2 = build_topology_viewer_html(initial, events)
        assert h1 == h2

    def test_output_non_empty(self, html_output):
        assert len(html_output) > 10_000, "HTML output seems too small"


class TestAdvisory:
    def test_advisory_banner_present(self, html_output):
        assert "Advisory" in html_output

    def test_advisory_text(self, html_output):
        assert "OEM" in html_output
