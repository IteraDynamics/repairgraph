"""
Tests for repairgraph.api.intake_routes.

Verifies that intake API endpoints return correct status codes, content types,
and usable payload structures. Also verifies existing endpoints are unaffected.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
FORD_PACKET = FIXTURES / "ford_packet"
MIXED_PACKET = FIXTURES / "mixed_packet"


def _read_fixture(path: Path) -> bytes:
    return path.read_bytes()


def _toyota_files() -> list[tuple]:
    """Build multipart file list from Toyota packet."""
    files = []
    for f in sorted(TOYOTA_PACKET.iterdir()):
        if f.is_file():
            files.append(("files", (f.name, f.read_bytes(), "text/plain")))
    return files


def _ford_files() -> list[tuple]:
    files = []
    for f in sorted(FORD_PACKET.iterdir()):
        if f.is_file():
            files.append(("files", (f.name, f.read_bytes(), "text/plain")))
    return files


# ── POST /internal/intake/classify ───────────────────────────────────────────

class TestIntakeClassifyEndpoint:
    def test_returns_200(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        assert response.status_code == 200

    def test_returns_json(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        assert "application/json" in response.headers["content-type"]

    def test_response_has_intake_id(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "intake_id" in data
        assert data["intake_id"].startswith("intake_")

    def test_response_has_readiness(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "readiness" in data
        assert data["readiness"] in ("ready", "partial", "incomplete", "unprocessable")

    def test_response_has_detected_packet(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "detected_packet" in data
        pkt = data["detected_packet"]
        assert "detected_oem" in pkt
        assert "detected_roles" in pkt

    def test_toyota_oem_detected(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert data["detected_packet"]["detected_oem"] == "Toyota"

    def test_response_has_files_list(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "files" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) == len(_toyota_files())

    def test_response_has_diagnostics(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "diagnostics" in data
        assert isinstance(data["diagnostics"], list)

    def test_response_has_missing_roles(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "missing_roles" in data

    def test_response_has_advisory(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "advisory" in data
        assert isinstance(data["advisory"], str)

    def test_response_has_endpoint_advisory(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "endpoint_advisory" in data

    def test_response_has_summary(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert "summary" in data
        summary = data["summary"]
        assert "readiness" in summary
        assert "file_count" in summary

    def test_ford_packet_returns_200(self):
        response = client.post("/internal/intake/classify", files=_ford_files())
        assert response.status_code == 200

    def test_ford_oem_detected(self):
        response = client.post("/internal/intake/classify", files=_ford_files())
        data = response.json()
        assert data["detected_packet"]["detected_oem"] == "Ford"

    def test_no_files_returns_422(self):
        response = client.post("/internal/intake/classify", files=[])
        assert response.status_code == 422

    def test_schema_name_in_response(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        assert data.get("schema_name") == "repairgraph.intake_manifest"

    def test_file_entries_have_required_fields(self):
        response = client.post("/internal/intake/classify", files=_toyota_files())
        data = response.json()
        for f in data["files"]:
            assert "file_id" in f
            assert "filename" in f
            assert "document_role" in f
            assert "confidence" in f

    def test_single_text_file(self):
        content = b"Toyota Motor Corporation 2023 Camry repair procedure removal installation step 1"
        response = client.post(
            "/internal/intake/classify",
            files=[("files", ("test.txt", content, "text/plain"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detected_packet"]["detected_oem"] == "Toyota"

    def test_malformed_content_handled(self):
        content = b"\x00\x01\x02\x03\xff\xfe binary garbage \x00"
        response = client.post(
            "/internal/intake/classify",
            files=[("files", ("binary.txt", content, "application/octet-stream"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert "intake_id" in data


# ── POST /internal/intake/report ──────────────────────────────────────────────

class TestIntakeReportEndpoint:
    def test_returns_200(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert response.status_code == 200

    def test_content_type_html(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "text/html" in response.headers["content-type"]

    def test_returns_valid_html(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text

    def test_contains_advisory_banner(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "advisory-banner" in response.text
        assert "Advisory" in response.text

    def test_contains_repairgraph_branding(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "RepairGraph" in response.text

    def test_contains_toyota_oem(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Toyota" in response.text

    def test_contains_intake_summary(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Intake Summary" in response.text

    def test_contains_diagnostics(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Diagnostic" in response.text

    def test_contains_readiness_section(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert "Readiness" in response.text

    def test_ford_report_returns_200(self):
        response = client.post("/internal/intake/report", files=_ford_files())
        assert response.status_code == 200

    def test_ford_report_contains_ford(self):
        response = client.post("/internal/intake/report", files=_ford_files())
        assert "Ford" in response.text

    def test_no_files_returns_422(self):
        response = client.post("/internal/intake/report", files=[])
        assert response.status_code == 422

    def test_no_external_cdn(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert 'src="http' not in response.text
        assert "cdn.jsdelivr" not in response.text

    def test_report_is_non_trivial(self):
        response = client.post("/internal/intake/report", files=_toyota_files())
        assert len(response.text) > 3000


# ── Existing endpoints unaffected ─────────────────────────────────────────────

class TestExistingEndpointsUnchanged:
    def test_state_initial(self):
        assert client.get("/internal/state/accord/initial").status_code == 200

    def test_state_projected(self):
        assert client.get("/internal/state/accord/projected").status_code == 200

    def test_state_summary(self):
        assert client.get("/internal/state/accord/summary").status_code == 200

    def test_state_report(self):
        r = client.get("/internal/state/accord/report")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_state_visualization(self):
        assert client.get("/internal/state/accord/visualization").status_code == 200
