"""Tests for GET /internal/review and GET /internal/review/payload endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


class TestReviewHTMLEndpoint:
    def test_returns_200(self):
        resp = client.get("/internal/review")
        assert resp.status_code == 200

    def test_returns_html(self):
        resp = client.get("/internal/review")
        assert "text/html" in resp.headers["content-type"]

    def test_html_contains_repair_review_heading(self):
        resp = client.get("/internal/review")
        assert "REPAIR REVIEW" in resp.text or "Repair Review" in resp.text

    def test_html_is_self_contained_no_cdn(self):
        resp = client.get("/internal/review")
        text = resp.text
        # Must not reference CDN or external JS
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text
        assert "googleapis.com" not in text

    def test_html_has_decision_section(self):
        resp = client.get("/internal/review")
        # Should answer can repair proceed
        assert "proceed" in resp.text.lower() or "blocked" in resp.text.lower()

    def test_html_contains_legal_advisory(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "advisory" in text

    def test_html_contains_oem_disclaimer(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "oem" in text

    def test_html_does_not_say_parser(self):
        resp = client.get("/internal/review")
        assert "parser" not in resp.text.lower()

    def test_html_does_not_say_json(self):
        resp = client.get("/internal/review")
        # The word JSON may appear in embedded data attributes but not in user-facing text
        # We check it doesn't appear in user-visible section headings
        assert "<h1>JSON" not in resp.text
        assert "<h2>JSON" not in resp.text
        assert "<h3>JSON" not in resp.text

    def test_html_mentions_honda_accord(self):
        resp = client.get("/internal/review")
        assert "Honda" in resp.text or "Accord" in resp.text

    def test_html_has_next_action(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "next action" in text or "recommended action" in text

    def test_html_has_evidence_section(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "evidence" in text

    def test_html_has_workflow_section(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "workflow" in text

    def test_html_has_export_buttons(self):
        resp = client.get("/internal/review")
        text = resp.text
        assert "Topology Viewer" in text or "topology" in text.lower()

    def test_html_no_framework_imports(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "react" not in text
        assert "vue" not in text
        assert "angular" not in text


class TestReviewPayloadEndpoint:
    def test_returns_200(self):
        resp = client.get("/internal/review/payload")
        assert resp.status_code == 200

    def test_returns_json(self):
        resp = client.get("/internal/review/payload")
        assert "application/json" in resp.headers["content-type"]

    def test_payload_has_required_sections(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        for key in ("header", "decision", "top_findings", "documentation",
                    "workflow_readiness", "evidence_trail", "export_links",
                    "advisory_notice"):
            assert key in data, f"Missing payload key: {key}"

    def test_payload_has_endpoint_advisory(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        assert "endpoint_advisory" in data

    def test_payload_decision_has_decision_field(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        decision = data.get("decision", {})
        assert "decision" in decision
        assert decision["decision"] in (
            "Blocked", "Proceed with Caution", "Ready to Proceed",
            "Needs Review", "Insufficient Packet"
        )

    def test_payload_header_has_oem(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        assert data["header"].get("oem") == "Honda"

    def test_payload_top_findings_at_most_five(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        top = data.get("top_findings", {}).get("top_findings", [])
        assert len(top) <= 5

    def test_payload_advisory_notice_non_empty(self):
        resp = client.get("/internal/review/payload")
        data = resp.json()
        assert data["advisory_notice"]


class TestExistingEndpointsUnaffected:
    """Regression: existing API routes must still work."""

    def test_demo_endpoint_unaffected(self):
        resp = client.get("/internal/demo")
        assert resp.status_code == 200

    def test_demo_payload_unaffected(self):
        resp = client.get("/internal/demo/payload")
        assert resp.status_code == 200

    def test_state_accord_summary_unaffected(self):
        resp = client.get("/internal/state/accord/summary")
        assert resp.status_code == 200

    def test_state_accord_projected_unaffected(self):
        resp = client.get("/internal/state/accord/projected")
        assert resp.status_code == 200

    def test_topology_viewer_unaffected(self):
        resp = client.get("/internal/state/accord/topology-viewer")
        assert resp.status_code == 200

    def test_intake_page_unaffected(self):
        resp = client.get("/internal/intake")
        assert resp.status_code == 200
