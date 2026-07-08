"""Tests for the home page — the single entry point tying intake, review,
progress, and fleet together at GET /.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.core.vehicle_store import (
    VehicleContext,
    clear_active_vehicle,
    set_active_vehicle,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_active_vehicle():
    clear_active_vehicle()
    yield
    clear_active_vehicle()


class TestHomePage:
    def test_returns_200_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_is_self_contained(self):
        text = client.get("/").text
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text
        assert "react" not in text.lower()

    def test_links_to_all_four_steps(self):
        text = client.get("/").text
        assert 'href="/internal/intake"' in text
        assert 'href="/internal/review"' in text
        assert 'href="/internal/review/progress/ui"' in text
        assert 'href="/internal/fleet/ui"' in text

    def test_has_advisory_notice(self):
        text = client.get("/").text
        assert "advisory" in text.lower()

    def test_no_active_vehicle_shows_no_active_job(self):
        text = client.get("/").text
        assert "No active job" in text

    def test_active_vehicle_is_shown_by_name(self):
        set_active_vehicle(VehicleContext(
            oem="Hyundai", year=2023, model="Elantra",
            operation="quarter_panel_replacement", source="intake", readiness="ready",
        ))
        text = client.get("/").text
        assert "Hyundai" in text
        assert "Elantra" in text
        assert "2023" in text
        assert "No active job" not in text

    def test_job_count_reflects_fleet_summary(self):
        from repairgraph.state.fleet import build_fleet_summary
        expected = build_fleet_summary()["job_count"]
        text = client.get("/").text
        assert f"<b>{expected}</b>" in text
