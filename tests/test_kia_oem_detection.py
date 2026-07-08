"""Regression test for a real bug found while preparing for evaluation:
Kia was not in the intake classifier's OEM vocabulary at all — it was
bucketed under the "Hyundai" pattern group (Hyundai Motor Group owns Kia),
so a Kia repair document was silently misdetected as OEM=Hyundai with no
model, since no Kia model names were registered either.

This is worse than an honest "unknown" — it actively mislabels the vehicle
brand. Fixed by giving Kia its own OEM entry and model vocabulary,
consistent with how every other brand in the classifier is structured.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.core.vehicle_store import clear_active_vehicle
from repairgraph.intake.classify import classify_intake_packet

client = TestClient(app)

KIA_DOC = """2024 Kia Sportage Quarter Panel Replacement

Before removal, inspect the rear pillar gutter for damage.
Replace the rear quarter outer panel and the wheel arch separator.
The rear quarter outer panel is adjacent to the quarter pillar stiffener.
Sectioning: make the cut along the front upper edge of the quarter panel,
30 mm from the pillar seam.
Joining: 8 spot welds along the upper flange. MIG brazing required
adjacent to the roof rail.
The quarter pillar stiffener is 1470 MPa hot-stamped steel.
Apply seam sealer to all joints.
"""


class TestKiaDetectedAsItsOwnBrand:
    def test_kia_detected_not_hyundai(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "2024_kia_sportage_quarter_panel_replacement.txt"
            doc.write_text(KIA_DOC)
            manifest = classify_intake_packet([doc])
        assert manifest.detected_packet.detected_oem == "Kia"

    def test_kia_model_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "2024_kia_sportage_quarter_panel_replacement.txt"
            doc.write_text(KIA_DOC)
            manifest = classify_intake_packet([doc])
        assert manifest.detected_packet.detected_model == "Sportage"

    def test_kia_year_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "2024_kia_sportage_quarter_panel_replacement.txt"
            doc.write_text(KIA_DOC)
            manifest = classify_intake_packet([doc])
        assert manifest.detected_packet.detected_year == 2024

    def test_common_kia_models_recognized(self):
        for model_text, expected in [
            ("2023 Kia Sorento repair procedure", "Sorento"),
            ("2023 Kia Telluride repair procedure", "Telluride"),
            ("2023 Kia Forte repair procedure", "Forte"),
            ("2023 Kia Soul repair procedure", "Soul"),
            ("2023 Kia K5 repair procedure", "K5"),
        ]:
            with tempfile.TemporaryDirectory() as tmp:
                doc = Path(tmp) / "kia_doc.txt"
                doc.write_text(model_text)
                manifest = classify_intake_packet([doc])
            assert manifest.detected_packet.detected_oem == "Kia", model_text
            assert manifest.detected_packet.detected_model == expected, model_text


class TestHyundaiAndGenesisUnaffectedByKiaFix:
    """Kia was carved out of the Hyundai pattern bucket — Hyundai and
    Genesis detection must be completely unchanged."""

    def test_hyundai_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "hyundai_doc.txt"
            doc.write_text("2023 Hyundai Elantra quarter panel replacement spot weld")
            manifest = classify_intake_packet([doc])
        assert manifest.detected_packet.detected_oem == "Hyundai"
        assert manifest.detected_packet.detected_model == "Elantra"

    def test_genesis_still_maps_to_hyundai_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "genesis_doc.txt"
            doc.write_text("2025 Genesis GV70 repair procedure spot weld")
            manifest = classify_intake_packet([doc])
        assert manifest.detected_packet.detected_oem == "Hyundai"


class TestKiaEndToEndThroughReviewAndFleet:
    def setup_method(self):
        clear_active_vehicle()

    def teardown_method(self):
        clear_active_vehicle()

    def test_kia_upload_produces_no_demo_notice(self):
        client.post(
            "/internal/intake/classify",
            files={"files": ("kia.txt", KIA_DOC.encode(), "text/plain")},
        )
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice' not in resp.text
        assert "Kia" in resp.text
        assert "Sportage" in resp.text

    def test_kia_job_appears_on_fleet_dashboard(self):
        client.post(
            "/internal/intake/classify",
            files={"files": ("kia.txt", KIA_DOC.encode(), "text/plain")},
        )
        resp = client.get("/internal/fleet/ui")
        assert "Kia" in resp.text
        assert "Sportage" in resp.text
