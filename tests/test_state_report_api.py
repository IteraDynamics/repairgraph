"""
Tests for the /internal/state/accord/report API endpoint.

Verifies that the endpoint returns 200, content-type text/html, and valid
self-contained HTML reports for both workflow and replay views.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


class TestReportEndpointDefaults:
    def test_returns_200(self):
        response = client.get("/internal/state/accord/report")
        assert response.status_code == 200

    def test_content_type_html(self):
        response = client.get("/internal/state/accord/report")
        assert "text/html" in response.headers["content-type"]

    def test_returns_non_empty_body(self):
        response = client.get("/internal/state/accord/report")
        assert len(response.text) > 1000

    def test_returns_valid_html_document(self):
        response = client.get("/internal/state/accord/report")
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text

    def test_contains_advisory_banner(self):
        response = client.get("/internal/state/accord/report")
        assert "advisory-banner" in response.text
        assert "Advisory" in response.text

    def test_contains_workflow_summary(self):
        response = client.get("/internal/state/accord/report")
        assert "Workflow Summary" in response.text

    def test_contains_repairgraph_branding(self):
        response = client.get("/internal/state/accord/report")
        assert "RepairGraph" in response.text

    def test_contains_accord(self):
        response = client.get("/internal/state/accord/report")
        assert "Accord" in response.text

    def test_contains_mermaid_section(self):
        response = client.get("/internal/state/accord/report")
        assert "mermaid-block" in response.text


class TestReportEndpointWorkflowView:
    def test_workflow_view_returns_200(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert response.status_code == 200

    def test_workflow_view_content_type_html(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert "text/html" in response.headers["content-type"]

    def test_workflow_view_contains_next_actions(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert "Next Recommended Actions" in response.text

    def test_workflow_view_contains_event_timeline(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert "Event Timeline" in response.text

    def test_workflow_view_contains_phase_overview(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert "Phase" in response.text

    def test_workflow_view_no_external_deps(self):
        response = client.get("/internal/state/accord/report?view=workflow")
        assert 'src="http' not in response.text
        assert "cdn" not in response.text.lower().split("<script")[0]


class TestReportEndpointReplayView:
    def test_replay_view_returns_200(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert response.status_code == 200

    def test_replay_view_content_type_html(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "text/html" in response.headers["content-type"]

    def test_replay_view_contains_replay_inspector(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "Replay Inspector" in response.text

    def test_replay_view_contains_replay_step_summary(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "Replay Step Summary" in response.text

    def test_replay_view_contains_js_replay_data(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "_replayData" in response.text
        assert "initReplay" in response.text

    def test_replay_view_contains_session_overview(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "Session Overview" in response.text

    def test_replay_view_contains_mermaid(self):
        response = client.get("/internal/state/accord/report?view=replay")
        assert "mermaid-block" in response.text


class TestReportEndpointDeterminism:
    def test_workflow_view_deterministic(self):
        r1 = client.get("/internal/state/accord/report?view=workflow")
        r2 = client.get("/internal/state/accord/report?view=workflow")
        assert r1.text == r2.text

    def test_replay_view_deterministic(self):
        r1 = client.get("/internal/state/accord/report?view=replay")
        r2 = client.get("/internal/state/accord/report?view=replay")
        assert r1.text == r2.text

    def test_default_matches_workflow_view(self):
        r_default = client.get("/internal/state/accord/report")
        r_workflow = client.get("/internal/state/accord/report?view=workflow")
        assert r_default.text == r_workflow.text


class TestExistingEndpointsUnchanged:
    """Verify existing API endpoints still return 200 after adding the report endpoint."""

    def test_initial_endpoint(self):
        assert client.get("/internal/state/accord/initial").status_code == 200

    def test_projected_endpoint(self):
        assert client.get("/internal/state/accord/projected").status_code == 200

    def test_ar_payload_endpoint(self):
        assert client.get("/internal/state/accord/ar-payload").status_code == 200

    def test_timeline_endpoint(self):
        assert client.get("/internal/state/accord/timeline").status_code == 200

    def test_replay_endpoint(self):
        assert client.get("/internal/state/accord/replay").status_code == 200

    def test_visualization_endpoint(self):
        assert client.get("/internal/state/accord/visualization").status_code == 200

    def test_summary_endpoint(self):
        assert client.get("/internal/state/accord/summary").status_code == 200
