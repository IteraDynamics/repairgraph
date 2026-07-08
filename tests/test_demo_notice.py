"""Tests for the demo-fallback honesty fix.

Previously, the review page silently rendered the built-in Honda Accord
demo whenever a real vehicle couldn't be resolved — including when a
viewer explicitly requested a vehicle that doesn't exist, or when an
intake upload's active-vehicle reference pointed at a procedure that was
never actually written. That reads as either a bug or as fabricated
results to anyone evaluating this tool with their own document.

The review page must now say plainly, and visibly, whenever it is showing
demo data instead of a resolved real vehicle.
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
def no_active_vehicle():
    """Every test starts with a clean active-vehicle slate."""
    clear_active_vehicle()
    yield
    clear_active_vehicle()


class TestNoUploadYet:
    """No query params, no active vehicle — the ordinary first-visit state."""

    def test_notice_is_shown(self):
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice' in resp.text

    def test_notice_says_demo_not_uploaded_data(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "built-in demo" in text or "sample repair" in text
        assert "not data you uploaded" in text

    def test_notice_links_to_intake(self):
        resp = client.get("/internal/review")
        assert '<a href="/internal/intake">' in resp.text

    def test_not_flagged_as_warn_style(self):
        # This is expected behavior, not an error — softer styling than the
        # "you asked for X, we showed Y instead" case.
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice rr-demo-notice-warn"' not in resp.text


class TestRequestedVehicleNotFound:
    """Explicit oem/year/model given but nothing normalized for it."""

    def test_warn_notice_is_shown(self):
        resp = client.get("/internal/review?oem=Toyota&year=1999&model=Nonexistent")
        assert '<div class="rr-demo-notice rr-demo-notice-warn"' in resp.text

    def test_notice_names_the_requested_vehicle(self):
        resp = client.get("/internal/review?oem=Toyota&year=1999&model=Nonexistent")
        assert "1999" in resp.text
        assert "Toyota" in resp.text
        assert "Nonexistent" in resp.text

    def test_notice_explains_this_is_not_what_was_requested(self):
        resp = client.get("/internal/review?oem=Toyota&year=1999&model=Nonexistent")
        text = resp.text.lower()
        assert "no saved procedure found" in text
        assert "not the vehicle you requested" in text

    def test_page_still_returns_200_with_demo_content(self):
        resp = client.get("/internal/review?oem=Toyota&year=1999&model=Nonexistent")
        assert resp.status_code == 200
        assert "Honda" in resp.text or "Accord" in resp.text


class TestActiveVehiclePointsAtMissingProcedure:
    """The active-vehicle file references a vehicle with no normalized
    procedure on disk (e.g. corrupted/stale state)."""

    def test_warn_notice_is_shown(self):
        set_active_vehicle(VehicleContext(
            oem="Ghost", year=1999, model="Nonexistent",
            operation="quarter_panel_replacement", source="intake",
        ))
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice rr-demo-notice-warn"' in resp.text
        assert "Ghost" in resp.text


class TestRealVehicleResolvedNoNotice:
    """When a real vehicle actually compiles, no demo notice should appear
    — the fix must not add noise to the working path."""

    def test_explicit_fixture_vehicle_has_no_notice(self):
        resp = client.get("/internal/review?oem=Honda&year=2025&model=Accord")
        assert '<div class="rr-demo-notice' not in resp.text

    def test_active_vehicle_set_to_real_fixture_has_no_notice(self):
        set_active_vehicle(VehicleContext(
            oem="Honda", year=2025, model="Civic",
            operation="quarter_panel_replacement", source="fixture", readiness="ready",
        ))
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice' not in resp.text

    def test_active_vehicle_set_to_intake_derived_vehicle_has_no_notice(self):
        set_active_vehicle(VehicleContext(
            oem="Hyundai", year=2023, model="Elantra",
            operation="quarter_panel_replacement", source="intake", readiness="ready",
        ))
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice' not in resp.text


class TestJSONEndpointsUnaffected:
    """The demo-notice fix is a review-page (HTML) concern. JSON endpoints
    keep their existing silent-fallback behavior — they're integration
    surfaces, not something a first-time evaluator reads cold."""

    def test_payload_endpoint_still_200s_on_missing_vehicle(self):
        resp = client.get("/internal/review/payload?oem=Toyota&year=1999&model=Nonexistent")
        assert resp.status_code == 200

    def test_payload_endpoint_has_no_demo_notice_field(self):
        resp = client.get("/internal/review/payload?oem=Toyota&year=1999&model=Nonexistent")
        assert "demo_notice" not in resp.json()
