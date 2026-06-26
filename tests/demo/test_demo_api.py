"""
Tests for the RepairGraph demo API endpoints.

Covers: HTTP status, content type, HTML correctness, JSON payload endpoint,
and regression against all existing endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)


class TestDemoEndpoint:
    def test_returns_200(self):
        r = client.get("/internal/demo")
        assert r.status_code == 200

    def test_content_type_html(self):
        r = client.get("/internal/demo")
        assert "text/html" in r.headers["content-type"]

    def test_response_non_empty(self):
        r = client.get("/internal/demo")
        assert len(r.text) > 10_000

    def test_contains_repairgraph(self):
        r = client.get("/internal/demo")
        assert "RepairGraph" in r.text

    def test_contains_honda_accord(self):
        r = client.get("/internal/demo")
        assert "Accord" in r.text

    def test_no_external_cdn(self):
        r = client.get("/internal/demo")
        assert "cdn." not in r.text.lower()

    def test_has_demo_payload_embedded(self):
        r = client.get("/internal/demo")
        assert "const DEMO" in r.text

    def test_has_step_elements(self):
        r = client.get("/internal/demo")
        for step_id in ("step-intake", "step-analysis", "step-intelligence",
                        "step-viewer", "step-replay", "step-summary", "step-export"):
            assert step_id in r.text, f"Missing step: {step_id}"

    def test_structurally_consistent(self):
        # intake_id is a random UUID per call — compare structural content not raw text
        r1 = client.get("/internal/demo")
        r2 = client.get("/internal/demo")
        assert r1.status_code == r2.status_code
        # Both should contain Honda Accord workflow data
        assert "Accord" in r1.text and "Accord" in r2.text
        assert "workflow_summary" in r1.text and "workflow_summary" in r2.text


class TestDemoPayloadEndpoint:
    def test_returns_200(self):
        r = client.get("/internal/demo/payload")
        assert r.status_code == 200

    def test_content_type_json(self):
        r = client.get("/internal/demo/payload")
        assert "application/json" in r.headers["content-type"]

    def test_schema_name(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert data["schema_name"] == "repairgraph.demo.full"

    def test_has_intake(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert "intake" in data

    def test_has_workflow(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert "workflow" in data

    def test_has_export_links(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert "export_links" in data

    def test_advisory_flag(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert data["advisory"] is True

    def test_workflow_summary_present(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert "workflow_summary" in data["workflow"]

    def test_intake_file_count_positive(self):
        r = client.get("/internal/demo/payload")
        data = r.json()
        assert data["intake"]["file_count"] > 0

    def test_is_deterministic(self):
        r1 = client.get("/internal/demo/payload")
        r2 = client.get("/internal/demo/payload")
        assert r1.json()["workflow"]["session"] == r2.json()["workflow"]["session"]


class TestExistingEndpointsRegression:
    """Regression: all existing endpoints must remain functional."""

    def test_state_initial(self):
        assert client.get("/internal/state/accord/initial").status_code == 200

    def test_state_projected(self):
        assert client.get("/internal/state/accord/projected").status_code == 200

    def test_state_ar_payload(self):
        assert client.get("/internal/state/accord/ar-payload").status_code == 200

    def test_state_timeline(self):
        assert client.get("/internal/state/accord/timeline").status_code == 200

    def test_state_replay(self):
        assert client.get("/internal/state/accord/replay").status_code == 200

    def test_state_visualization(self):
        assert client.get("/internal/state/accord/visualization").status_code == 200

    def test_state_report_workflow(self):
        assert client.get("/internal/state/accord/report?view=workflow").status_code == 200

    def test_state_report_replay(self):
        assert client.get("/internal/state/accord/report?view=replay").status_code == 200

    def test_state_summary(self):
        assert client.get("/internal/state/accord/summary").status_code == 200

    def test_topology_viewer(self):
        assert client.get("/internal/state/accord/topology-viewer").status_code == 200

    def test_intake_page(self):
        assert client.get("/internal/intake").status_code == 200
