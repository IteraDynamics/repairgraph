"""
Tests for repairgraph.intake.upload_page and GET /internal/intake.

Verifies that the upload page is valid self-contained HTML, references the
correct endpoints, includes required UI sections, contains advisory language,
and has no external CDN dependencies.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.intake.upload_page import build_intake_upload_page

client = TestClient(app)


# ── build_intake_upload_page (unit) ──────────────────────────────────────────

class TestBuildIntakeUploadPage:
    def test_returns_string(self):
        page = build_intake_upload_page()
        assert isinstance(page, str)

    def test_is_valid_html_structure(self):
        page = build_intake_upload_page()
        assert "<!DOCTYPE html>" in page
        assert "<html" in page
        assert "</html>" in page
        assert "<head>" in page
        assert "</head>" in page
        assert "<body>" in page
        assert "</body>" in page

    def test_has_file_input(self):
        page = build_intake_upload_page()
        assert 'type="file"' in page
        assert 'id="file-input"' in page

    def test_accepts_multiple_files(self):
        page = build_intake_upload_page()
        assert "multiple" in page

    def test_has_drop_zone(self):
        page = build_intake_upload_page()
        assert 'id="drop-zone"' in page
        assert "drag" in page.lower()

    def test_references_classify_endpoint(self):
        page = build_intake_upload_page()
        assert "/internal/intake/classify" in page

    def test_references_report_endpoint(self):
        page = build_intake_upload_page()
        assert "/internal/intake/report" in page

    def test_has_analyze_button(self):
        page = build_intake_upload_page()
        assert "analyzeFiles" in page
        assert "btn-analyze" in page

    def test_has_report_button(self):
        page = build_intake_upload_page()
        assert "viewReport" in page
        assert "btn-report" in page

    def test_has_results_area(self):
        page = build_intake_upload_page()
        assert 'id="results"' in page

    def test_has_loading_indicator(self):
        page = build_intake_upload_page()
        assert "loading" in page.lower()

    def test_has_error_area(self):
        page = build_intake_upload_page()
        assert 'id="error-area"' in page

    def test_has_advisory_language(self):
        page = build_intake_upload_page()
        assert "Advisory" in page
        assert "authorized" in page
        assert "OEM" in page

    def test_not_oem_distribution_platform(self):
        page = build_intake_upload_page()
        assert "not an OEM document distribution platform" in page

    def test_no_external_cdn(self):
        page = build_intake_upload_page()
        assert "cdn." not in page
        assert 'src="http' not in page
        assert "jsdelivr" not in page
        assert "unpkg.com" not in page
        assert "cloudflare" not in page

    def test_has_inline_css(self):
        page = build_intake_upload_page()
        assert "<style>" in page

    def test_has_inline_js(self):
        page = build_intake_upload_page()
        assert "<script>" in page

    def test_no_external_script_src(self):
        page = build_intake_upload_page()
        # No <script src="http..."> or <script src="//...">
        import re
        external = re.findall(r'<script[^>]+src=["\'](?:https?:|//)', page)
        assert external == []

    def test_uses_fetch_api(self):
        page = build_intake_upload_page()
        assert "fetch(" in page

    def test_uses_formdata(self):
        page = build_intake_upload_page()
        assert "FormData" in page

    def test_opens_report_in_new_tab(self):
        page = build_intake_upload_page()
        assert "window.open" in page
        assert "_blank" in page

    def test_has_repairgraph_branding(self):
        page = build_intake_upload_page()
        assert "RepairGraph" in page

    def test_deterministic(self):
        p1 = build_intake_upload_page()
        p2 = build_intake_upload_page()
        assert p1 == p2

    def test_non_trivial_length(self):
        page = build_intake_upload_page()
        assert len(page) > 3000

    def test_has_file_list_area(self):
        page = build_intake_upload_page()
        assert 'id="file-list"' in page

    def test_local_internal_caveat(self):
        page = build_intake_upload_page()
        assert "local" in page.lower() or "internal" in page.lower()

    def test_supported_formats_mentioned(self):
        page = build_intake_upload_page()
        assert ".txt" in page

    def test_drag_drop_events_wired(self):
        page = build_intake_upload_page()
        assert "dragover" in page
        assert "drop" in page


# ── GET /internal/intake (API) ───────────────────────────────────────────────

class TestIntakeUploadPageEndpoint:
    def test_returns_200(self):
        response = client.get("/internal/intake")
        assert response.status_code == 200

    def test_content_type_html(self):
        response = client.get("/internal/intake")
        assert "text/html" in response.headers["content-type"]

    def test_returns_valid_html(self):
        response = client.get("/internal/intake")
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text

    def test_has_file_input(self):
        response = client.get("/internal/intake")
        assert 'type="file"' in response.text

    def test_references_classify_endpoint(self):
        response = client.get("/internal/intake")
        assert "/internal/intake/classify" in response.text

    def test_references_report_endpoint(self):
        response = client.get("/internal/intake")
        assert "/internal/intake/report" in response.text

    def test_has_advisory_language(self):
        response = client.get("/internal/intake")
        assert "Advisory" in response.text
        assert "authorized" in response.text

    def test_not_oem_distribution_platform(self):
        response = client.get("/internal/intake")
        assert "not an OEM document distribution platform" in response.text

    def test_no_external_cdn(self):
        response = client.get("/internal/intake")
        assert "cdn." not in response.text
        assert "jsdelivr" not in response.text
        assert 'src="http' not in response.text

    def test_has_repairgraph_branding(self):
        response = client.get("/internal/intake")
        assert "RepairGraph" in response.text

    def test_has_upload_section(self):
        response = client.get("/internal/intake")
        assert "Upload" in response.text

    def test_non_trivial(self):
        response = client.get("/internal/intake")
        assert len(response.text) > 3000

    def test_has_analyze_button(self):
        response = client.get("/internal/intake")
        assert "Analyze" in response.text

    def test_has_report_button(self):
        response = client.get("/internal/intake")
        assert "Report" in response.text


# ── Existing POST endpoints unaffected ───────────────────────────────────────

class TestExistingIntakeEndpointsUnaffected:
    def _toyota_files(self):
        from pathlib import Path
        fixtures = Path(__file__).parent / "fixtures" / "intake" / "toyota_packet"
        return [
            ("files", (f.name, f.read_bytes(), "text/plain"))
            for f in sorted(fixtures.iterdir()) if f.is_file()
        ]

    def test_classify_still_200(self):
        response = client.post("/internal/intake/classify", files=self._toyota_files())
        assert response.status_code == 200

    def test_report_still_200(self):
        response = client.post("/internal/intake/report", files=self._toyota_files())
        assert response.status_code == 200

    def test_classify_returns_json(self):
        response = client.post("/internal/intake/classify", files=self._toyota_files())
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        assert "intake_id" in data

    def test_report_returns_html(self):
        response = client.post("/internal/intake/report", files=self._toyota_files())
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
