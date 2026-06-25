"""
Tests for the topology viewer API endpoint.

Covers: HTTP response, content type, HTML structure, and regression against
existing endpoints to ensure nothing was broken.
"""
import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


class TestTopologyViewerEndpoint:
    def test_returns_200(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert response.status_code == 200

    def test_content_type_html(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "text/html" in response.headers["content-type"]

    def test_response_is_non_empty(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert len(response.text) > 5000

    def test_contains_repairgraph_title(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "RepairGraph" in response.text

    def test_contains_accord(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "Accord" in response.text

    def test_contains_svg_vehicle(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "<svg" in response.text

    def test_contains_vehicle_regions(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "region_hood" in response.text
        assert "region_roof" in response.text

    def test_no_external_dependencies(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "cdn." not in response.text.lower()
        assert "react" not in response.text.lower()

    def test_contains_embedded_payload(self):
        response = client.get("/internal/state/accord/topology-viewer")
        assert "const PAYLOAD" in response.text

    def test_is_self_contained(self):
        response = client.get("/internal/state/accord/topology-viewer")
        html = response.text
        assert "<style>" in html
        assert "<script>" in html

    def test_is_deterministic(self):
        r1 = client.get("/internal/state/accord/topology-viewer")
        r2 = client.get("/internal/state/accord/topology-viewer")
        assert r1.text == r2.text


class TestExistingEndpointsNotBroken:
    """Regression: ensure existing state endpoints still work."""

    def test_initial_state(self):
        r = client.get("/internal/state/accord/initial")
        assert r.status_code == 200
        data = r.json()
        assert "session" in data

    def test_projected_state(self):
        r = client.get("/internal/state/accord/projected")
        assert r.status_code == 200

    def test_timeline(self):
        r = client.get("/internal/state/accord/timeline")
        assert r.status_code == 200

    def test_replay(self):
        r = client.get("/internal/state/accord/replay")
        assert r.status_code == 200

    def test_visualization(self):
        r = client.get("/internal/state/accord/visualization")
        assert r.status_code == 200

    def test_report_workflow(self):
        r = client.get("/internal/state/accord/report?view=workflow")
        assert r.status_code == 200

    def test_report_replay(self):
        r = client.get("/internal/state/accord/report?view=replay")
        assert r.status_code == 200

    def test_summary(self):
        r = client.get("/internal/state/accord/summary")
        assert r.status_code == 200
