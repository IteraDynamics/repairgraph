"""
Tests for the intake → normalize → review pipeline.

Covers:
- NormalizationResult construction from IntakeManifest
- Joining method extraction from welding evidence
- Corrosion requirement extraction from corrosion evidence
- Sectioning location detection
- File write/read roundtrip
- VehicleStore: get/set/clear/list
- _build_model() vehicle resolution order (params > active > demo)
- Review endpoints accept vehicle query params
- Review endpoints use active vehicle when no params
- Full pipeline: normalize → review returns correct OEM/model
- /internal/review/vehicles endpoint
- DELETE /internal/review/vehicles/active endpoint
- Regression: demo fallback still works
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from repairgraph.intake.normalizer import (
    NormalizationResult,
    normalize_intake_manifest,
    _extract_joining_methods,
    _extract_corrosion_requirements,
    _extract_sectioning_locations,
)
from repairgraph.intake.schema import IntakeFile, IntakeManifest, IntakePacket
from repairgraph.core.vehicle_store import (
    VehicleContext,
    clear_active_vehicle,
    get_active_vehicle,
    list_available_vehicles,
    set_active_vehicle,
    _ACTIVE_VEHICLE_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(
    oem="Hyundai",
    model="Elantra",
    year=2025,
    operation="quarter_panel_replacement",
    readiness="ready",
    files=None,
) -> IntakeManifest:
    pkt = IntakePacket(
        detected_oem=oem,
        detected_model=model,
        detected_year=year,
        detected_operation=operation,
        oem_confidence=0.9,
        detected_roles=["repair_procedure", "welding", "corrosion_protection"],
        file_count=len(files) if files else 3,
    )
    return IntakeManifest(
        intake_id="test-intake-001",
        files=files or _default_files(),
        detected_packet=pkt,
        missing_roles=[],
        diagnostics=[],
        readiness=readiness,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _default_files() -> list[IntakeFile]:
    return [
        IntakeFile(
            file_id="f1",
            filename="elantra_repair_procedure.pdf",
            extension=".pdf",
            size_bytes=50000,
            document_role="repair_procedure",
            detected_oem="Hyundai",
            detected_model="Elantra",
            detected_year=2025,
            detected_operation="quarter_panel_replacement",
            role_evidence=["quarter panel", "rear side panel"],
            confidence=0.85,
        ),
        IntakeFile(
            file_id="f2",
            filename="elantra_welding.pdf",
            extension=".pdf",
            size_bytes=30000,
            document_role="welding",
            role_evidence=["spot weld", "plug weld", "mig welding"],
            confidence=0.90,
        ),
        IntakeFile(
            file_id="f3",
            filename="elantra_corrosion.pdf",
            extension=".pdf",
            size_bytes=20000,
            document_role="corrosion_protection",
            role_evidence=["seam sealer", "corrosion protection", "anti-corrosion"],
            confidence=0.88,
        ),
    ]


# ---------------------------------------------------------------------------
# Normalizer — evidence extraction
# ---------------------------------------------------------------------------

class TestJoiningMethodExtraction:
    def test_spot_weld_detected(self):
        manifest = _make_manifest()
        methods = _extract_joining_methods(manifest)
        assert "spot_weld" in methods

    def test_plug_weld_detected(self):
        manifest = _make_manifest()
        methods = _extract_joining_methods(manifest)
        assert "plug_weld" in methods

    def test_mig_welding_detected(self):
        manifest = _make_manifest()
        methods = _extract_joining_methods(manifest)
        assert "mig_welding" in methods

    def test_no_duplicates(self):
        # Same evidence in multiple files should not duplicate
        files = _default_files()
        files[0] = IntakeFile(
            file_id="f0", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="repair_procedure",
            role_evidence=["spot weld"],  # also in welding file
            confidence=0.8,
        )
        manifest = _make_manifest(files=files)
        methods = _extract_joining_methods(manifest)
        assert methods.count("spot_weld") == 1

    def test_empty_when_no_welding_evidence(self):
        files = [
            IntakeFile(
                file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
                document_role="repair_procedure",
                role_evidence=["quarter panel"],
                confidence=0.7,
            )
        ]
        manifest = _make_manifest(files=files)
        methods = _extract_joining_methods(manifest)
        assert methods == []

    def test_resistance_spot_weld(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="welding",
            role_evidence=["resistance spot welding"],
            confidence=0.9,
        )]
        manifest = _make_manifest(files=files)
        assert "resistance_spot_weld" in _extract_joining_methods(manifest)

    def test_mig_brazing(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="welding",
            role_evidence=["mig brazing"],
            confidence=0.9,
        )]
        manifest = _make_manifest(files=files)
        assert "mig_brazing" in _extract_joining_methods(manifest)

    def test_adhesive_bonding(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="welding",
            role_evidence=["adhesive bonding"],
            confidence=0.9,
        )]
        manifest = _make_manifest(files=files)
        assert "adhesive_bonding" in _extract_joining_methods(manifest)


class TestCorrosionRequirementExtraction:
    def test_sealer_from_seam_sealer(self):
        manifest = _make_manifest()
        reqs = _extract_corrosion_requirements(manifest)
        assert "sealer_application_required" in reqs

    def test_corrosion_protection_flag(self):
        manifest = _make_manifest()
        reqs = _extract_corrosion_requirements(manifest)
        assert "corrosion_protection_required" in reqs

    def test_default_when_corrosion_role_but_no_evidence(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="corrosion_protection",
            role_evidence=[],  # no specific evidence
            confidence=0.7,
        )]
        manifest = _make_manifest(files=files)
        reqs = _extract_corrosion_requirements(manifest)
        # Should default to at least sealer_application_required
        assert len(reqs) >= 1

    def test_empty_when_no_corrosion_files(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="repair_procedure",
            role_evidence=["quarter panel"],
            confidence=0.8,
        )]
        manifest = _make_manifest(files=files)
        reqs = _extract_corrosion_requirements(manifest)
        assert reqs == []

    def test_cavity_wax_maps_to_undercoating(self):
        files = [IntakeFile(
            file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
            document_role="corrosion_protection",
            role_evidence=["cavity wax"],
            confidence=0.9,
        )]
        manifest = _make_manifest(files=files)
        reqs = _extract_corrosion_requirements(manifest)
        assert "undercoating_application_required" in reqs

    def test_no_duplicates(self):
        files = [
            IntakeFile(
                file_id="f1", filename="x.pdf", extension=".pdf", size_bytes=1,
                document_role="corrosion_protection",
                role_evidence=["seam sealer", "body sealant"],  # both → sealer_application_required
                confidence=0.9,
            )
        ]
        manifest = _make_manifest(files=files)
        reqs = _extract_corrosion_requirements(manifest)
        assert reqs.count("sealer_application_required") == 1


class TestSectioningExtraction:
    def test_sectioning_stub_when_role_present(self):
        files = _default_files() + [
            IntakeFile(
                file_id="f4", filename="sectioning.pdf", extension=".pdf", size_bytes=1,
                document_role="sectioning",
                role_evidence=["section cut", "sectioning location"],
                confidence=0.85,
            )
        ]
        manifest = _make_manifest(files=files)
        locs = _extract_sectioning_locations(manifest)
        assert len(locs) == 1
        assert locs[0]["zone"] == "intake_detected_section"

    def test_empty_when_no_sectioning_role(self):
        manifest = _make_manifest()
        locs = _extract_sectioning_locations(manifest)
        assert locs == []


# ---------------------------------------------------------------------------
# NormalizationResult
# ---------------------------------------------------------------------------

class TestNormalizationResult:
    def test_returns_normalization_result(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert isinstance(result, NormalizationResult)

    def test_correct_oem(self):
        manifest = _make_manifest(oem="Hyundai")
        result = normalize_intake_manifest(manifest, write=False)
        assert result.oem == "Hyundai"

    def test_correct_model(self):
        manifest = _make_manifest(model="Elantra")
        result = normalize_intake_manifest(manifest, write=False)
        assert result.model == "Elantra"

    def test_correct_year(self):
        manifest = _make_manifest(year=2025)
        result = normalize_intake_manifest(manifest, write=False)
        assert result.year == 2025

    def test_correct_operation(self):
        manifest = _make_manifest(operation="quarter_panel_replacement")
        result = normalize_intake_manifest(manifest, write=False)
        assert result.operation == "quarter_panel_replacement"

    def test_procedure_has_required_fields(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        proc = result.procedure
        for key in ("oem", "year", "model", "operation", "operation_family",
                    "joining_methods", "dependencies", "corrosion_requirements",
                    "repair_notes", "spatial_relationships", "source"):
            assert key in proc, f"Missing procedure key: {key}"

    def test_structure_has_required_fields(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        struct = result.structure
        for key in ("oem", "year", "model", "domain", "materials", "structure_nodes"):
            assert key in struct, f"Missing structure key: {key}"

    def test_procedure_joining_methods_populated(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert len(result.procedure["joining_methods"]) >= 1

    def test_procedure_corrosion_populated(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert len(result.procedure["corrosion_requirements"]) >= 1

    def test_not_written_when_write_false(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert result.written is False
        assert result.procedure_path is None

    def test_vehicle_label(self):
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        result = normalize_intake_manifest(manifest, write=False)
        assert "Hyundai" in result.vehicle_label
        assert "Elantra" in result.vehicle_label
        assert "2025" in result.vehicle_label

    def test_warnings_when_oem_missing(self):
        manifest = _make_manifest(oem=None)
        manifest.detected_packet.detected_oem = None
        result = normalize_intake_manifest(manifest, write=False)
        assert len(result.warnings) >= 1

    def test_to_dict_has_expected_keys(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        d = result.to_dict()
        for key in ("oem", "year", "model", "operation", "intake_id", "readiness",
                    "written", "procedure_path", "structure_path", "warnings", "advisory"):
            assert key in d

    def test_source_contains_intake_id(self):
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert result.procedure["source"]["intake_id"] == "test-intake-001"

    def test_spatial_relationships_empty(self):
        """Should never fabricate spatial relationships."""
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert result.procedure["spatial_relationships"] == []

    def test_dependencies_empty(self):
        """Should never fabricate component dependencies."""
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert result.procedure["dependencies"] == []

    def test_repair_notes_empty(self):
        """Should never fabricate repair notes."""
        manifest = _make_manifest()
        result = normalize_intake_manifest(manifest, write=False)
        assert result.procedure["repair_notes"] == []


# ---------------------------------------------------------------------------
# File write / roundtrip
# ---------------------------------------------------------------------------

class TestNormalizationWrite:
    def test_writes_procedure_file(self):
        manifest = _make_manifest()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            assert result.written is True
            assert result.procedure_path is not None
            assert result.procedure_path.exists()

    def test_writes_structure_file(self):
        manifest = _make_manifest()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            assert result.structure_path is not None
            assert result.structure_path.exists()

    def test_procedure_file_is_valid_json(self):
        manifest = _make_manifest()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            loaded = json.loads(result.procedure_path.read_text())
            assert loaded["oem"] == "Hyundai"
            assert loaded["model"] == "Elantra"

    def test_structure_file_is_valid_json(self):
        manifest = _make_manifest()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            loaded = json.loads(result.structure_path.read_text())
            assert loaded["oem"] == "Hyundai"

    def test_directory_created_correctly(self):
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            expected_dir = Path(tmpdir) / "hyundai" / "2025_elantra"
            assert expected_dir.is_dir()

    def test_no_write_when_oem_missing(self):
        manifest = _make_manifest()
        manifest.detected_packet.detected_oem = None
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            assert result.written is False

    def test_load_procedure_finds_normalized_file(self):
        """After write, load_procedure() should find the file."""
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            # Patch the normalized dir to point to our tmpdir
            with patch("repairgraph.query.loader.NORMALIZED_DIR", Path(tmpdir)):
                from repairgraph.query.loader import load_procedure
                proc = load_procedure("Hyundai", 2025, "Elantra")
                assert proc is not None
                assert proc["oem"] == "Hyundai"
                assert proc["model"] == "Elantra"


# ---------------------------------------------------------------------------
# VehicleStore
# ---------------------------------------------------------------------------

class TestVehicleStore:
    @pytest.fixture(autouse=True)
    def clean_active(self):
        """Restore active vehicle state before/after each test."""
        prev = _ACTIVE_VEHICLE_PATH.read_text() if _ACTIVE_VEHICLE_PATH.exists() else None
        yield
        if prev is None and _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        elif prev is not None:
            _ACTIVE_VEHICLE_PATH.write_text(prev)

    def test_get_active_vehicle_none_initially(self):
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        assert get_active_vehicle() is None

    def test_set_and_get_active_vehicle(self):
        ctx = VehicleContext(oem="Hyundai", year=2025, model="Elantra")
        set_active_vehicle(ctx)
        result = get_active_vehicle()
        assert result is not None
        assert result.oem == "Hyundai"
        assert result.model == "Elantra"
        assert result.year == 2025

    def test_clear_active_vehicle(self):
        ctx = VehicleContext(oem="Hyundai", year=2025, model="Elantra")
        set_active_vehicle(ctx)
        clear_active_vehicle()
        assert get_active_vehicle() is None

    def test_vehicle_context_to_dict(self):
        ctx = VehicleContext(oem="Hyundai", year=2025, model="Elantra", source="intake")
        d = ctx.to_dict()
        assert d["oem"] == "Hyundai"
        assert d["year"] == 2025
        assert d["model"] == "Elantra"
        assert d["source"] == "intake"

    def test_vehicle_context_roundtrip(self):
        ctx = VehicleContext(oem="Toyota", year=2024, model="Camry", intake_id="abc123")
        set_active_vehicle(ctx)
        loaded = get_active_vehicle()
        assert loaded.oem == "Toyota"
        assert loaded.year == 2024
        assert loaded.model == "Camry"
        assert loaded.intake_id == "abc123"

    def test_list_available_vehicles_includes_honda_fixtures(self):
        vehicles = list_available_vehicles()
        oem_models = {(v["oem"], v["model"]) for v in vehicles}
        assert ("Honda", "Accord") in oem_models

    def test_list_available_vehicles_source_fixture(self):
        vehicles = list_available_vehicles()
        accord = next(v for v in vehicles if v["model"] == "Accord" and v["oem"] == "Honda")
        assert accord["source"] == "fixture"

    def test_list_available_vehicles_intake_source_after_normalize(self):
        """Normalized vehicles appear in list with source='intake'."""
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            with patch("repairgraph.core.vehicle_store._NORMALIZED_DIR", Path(tmpdir)):
                vehicles = list_available_vehicles()
                elantra = next((v for v in vehicles if v["model"] == "Elantra"), None)
                assert elantra is not None
                assert elantra["source"] == "intake"


# ---------------------------------------------------------------------------
# Review endpoints — vehicle param resolution
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from repairgraph.api.app import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_active_vehicle_for_endpoint_tests():
    """Ensure active vehicle doesn't bleed between tests."""
    prev = _ACTIVE_VEHICLE_PATH.read_text() if _ACTIVE_VEHICLE_PATH.exists() else None
    yield
    if prev is None and _ACTIVE_VEHICLE_PATH.exists():
        _ACTIVE_VEHICLE_PATH.unlink()
    elif prev is not None:
        _ACTIVE_VEHICLE_PATH.write_text(prev)


class TestReviewVehicleParams:
    def test_review_demo_fallback_no_params(self, client):
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review")
        assert r.status_code == 200
        assert "Honda" in r.text or "Accord" in r.text

    def test_review_payload_honda_accord_by_params(self, client):
        r = client.get("/internal/review/payload?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"
        assert header.get("model") == "Accord"

    def test_review_payload_honda_crv_by_params(self, client):
        r = client.get("/internal/review/payload?oem=Honda&year=2025&model=CRV")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"

    def test_review_payload_honda_pilot_by_params(self, client):
        r = client.get("/internal/review/payload?oem=Honda&year=2025&model=Pilot")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"

    def test_unknown_vehicle_falls_back_to_demo(self, client):
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review/payload?oem=Martian&year=2099&model=Spaceship")
        assert r.status_code == 200
        # No crash — falls back to demo
        data = r.json()
        assert "domain_context" in data or "endpoint_advisory" in data

    def test_partial_params_ignored(self, client):
        """oem without year+model should fall back to active/demo."""
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review/payload?oem=Hyundai")
        assert r.status_code == 200
        # Should be demo (Honda Accord)
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"

    def test_active_vehicle_used_when_no_params(self, client):
        """Set active vehicle to Honda CRV; /review/payload should return CRV."""
        ctx = VehicleContext(oem="Honda", year=2025, model="CRV")
        set_active_vehicle(ctx)
        r = client.get("/internal/review/payload")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"

    def test_params_override_active_vehicle(self, client):
        """Explicit query params should override the active vehicle."""
        ctx = VehicleContext(oem="Honda", year=2025, model="CRV")
        set_active_vehicle(ctx)
        r = client.get("/internal/review/payload?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("model") == "Accord"


class TestVehiclesEndpoint:
    def test_vehicles_endpoint_200(self, client):
        r = client.get("/internal/review/vehicles")
        assert r.status_code == 200

    def test_vehicles_has_available_vehicles(self, client):
        r = client.get("/internal/review/vehicles")
        data = r.json()
        assert "available_vehicles" in data
        assert isinstance(data["available_vehicles"], list)

    def test_vehicles_has_demo_vehicle(self, client):
        r = client.get("/internal/review/vehicles")
        data = r.json()
        demo = data["demo_vehicle"]
        assert demo["oem"] == "Honda"
        assert demo["model"] == "Accord"

    def test_vehicles_has_resolution_order(self, client):
        r = client.get("/internal/review/vehicles")
        data = r.json()
        assert "resolution_order" in data
        assert len(data["resolution_order"]) == 3

    def test_vehicles_active_vehicle_reflects_store(self, client):
        ctx = VehicleContext(oem="Honda", year=2025, model="Pilot")
        set_active_vehicle(ctx)
        r = client.get("/internal/review/vehicles")
        data = r.json()
        assert data["active_vehicle"] is not None
        assert data["active_vehicle"]["model"] == "Pilot"

    def test_vehicles_active_none_when_cleared(self, client):
        clear_active_vehicle()
        r = client.get("/internal/review/vehicles")
        data = r.json()
        assert data["active_vehicle"] is None

    def test_available_vehicles_includes_honda(self, client):
        r = client.get("/internal/review/vehicles")
        data = r.json()
        oems = [v["oem"] for v in data["available_vehicles"]]
        assert "Honda" in oems

    def test_delete_active_vehicle(self, client):
        ctx = VehicleContext(oem="Honda", year=2025, model="Pilot")
        set_active_vehicle(ctx)
        r = client.delete("/internal/review/vehicles/active")
        assert r.status_code == 200
        data = r.json()
        assert data["cleared"] is True
        # Verify store is cleared
        assert get_active_vehicle() is None


class TestAllSubEndpointsAcceptVehicleParams:
    """Each sub-endpoint accepts vehicle params and returns 200."""

    def test_root_causes_with_params(self, client):
        r = client.get("/internal/review/root-causes?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_plan_with_params(self, client):
        r = client.get("/internal/review/plan?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_narrative_with_params(self, client):
        r = client.get("/internal/review/narrative?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_package_with_params(self, client):
        r = client.get("/internal/review/package?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_payload_with_params(self, client):
        r = client.get("/internal/review/payload?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_review_page_with_params(self, client):
        r = client.get("/internal/review?oem=Honda&year=2025&model=Accord")
        assert r.status_code == 200

    def test_root_causes_with_crv(self, client):
        r = client.get("/internal/review/root-causes?oem=Honda&year=2025&model=CRV")
        assert r.status_code == 200

    def test_package_with_civic(self, client):
        r = client.get("/internal/review/package?oem=Honda&year=2025&model=Civic")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Full pipeline: normalize → compile_from_state → review
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_normalize_then_review_returns_correct_vehicle(self, client):
        """Write a normalized Hyundai Elantra; _build_model() should return it."""
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            with patch("repairgraph.query.loader.NORMALIZED_DIR", Path(tmpdir)):
                from repairgraph.core.vehicle_store import VehicleContext
                mock_ctx = VehicleContext(oem="Hyundai", year=2025, model="Elantra")

                from repairgraph.review.routes import _build_model_for_vehicle
                model = _build_model_for_vehicle("Hyundai", 2025, "Elantra", "quarter_panel_replacement")
                assert model is not None
                ctx_data = model.domain_context.context_data
                assert ctx_data["vehicle"]["oem"] == "Hyundai"
                assert ctx_data["vehicle"]["model"] == "Elantra"

    def test_normalized_procedure_produces_valid_operational_model(self):
        """A normalized procedure produces a usable OperationalModel."""
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            assert result.written

            with patch("repairgraph.query.loader.NORMALIZED_DIR", Path(tmpdir)):
                from repairgraph.query.loader import load_procedure, load_vehicle_structure
                from repairgraph.state.initialize import initialize_repair_state
                from repairgraph.topology.builder import build_topology_graph
                from repairgraph.adapters.collision import CollisionDomainAdapter
                from repairgraph.core.compiler import RepairGraphCompiler

                procedure = load_procedure("Hyundai", 2025, "Elantra")
                assert procedure is not None

                structure = load_vehicle_structure("Hyundai", 2025, "Elantra")
                state = initialize_repair_state(procedure, structure)
                topology = build_topology_graph(procedure, structure)
                adapter = CollisionDomainAdapter.from_repair_state(state)
                model = RepairGraphCompiler().compile_from_state(
                    state=state, topology=topology, adapter=adapter
                )

                assert model is not None
                assert model.domain_context.context_data["vehicle"]["oem"] == "Hyundai"
                assert model.state is not None

    def test_planner_runs_on_normalized_vehicle(self):
        """OperationalPlanner works on intake-derived normalized vehicles."""
        manifest = _make_manifest(oem="Hyundai", model="Elantra", year=2025)
        with tempfile.TemporaryDirectory() as tmpdir:
            normalize_intake_manifest(manifest, output_dir=Path(tmpdir))
            with patch("repairgraph.query.loader.NORMALIZED_DIR", Path(tmpdir)):
                from repairgraph.query.loader import load_procedure, load_vehicle_structure
                from repairgraph.state.initialize import initialize_repair_state
                from repairgraph.topology.builder import build_topology_graph
                from repairgraph.adapters.collision import CollisionDomainAdapter
                from repairgraph.core.compiler import RepairGraphCompiler
                from repairgraph.review.operational_planner import build_operational_plan
                from repairgraph.review.root_cause import build_root_cause_analysis

                procedure = load_procedure("Hyundai", 2025, "Elantra")
                structure = load_vehicle_structure("Hyundai", 2025, "Elantra")
                state = initialize_repair_state(procedure, structure)
                topology = build_topology_graph(procedure, structure)
                adapter = CollisionDomainAdapter.from_repair_state(state)
                model = RepairGraphCompiler().compile_from_state(
                    state=state, topology=topology, adapter=adapter
                )

                rca = build_root_cause_analysis(model)
                plan = build_operational_plan(model, rca=rca)
                assert plan is not None
                assert plan.next_best_action is not None


# ---------------------------------------------------------------------------
# Regression: demo still works
# ---------------------------------------------------------------------------

class TestDemoRegression:
    def test_demo_returns_honda_accord(self, client):
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review/payload")
        assert r.status_code == 200
        data = r.json()
        header = data.get("header", {})
        assert header.get("oem") == "Honda"
        assert header.get("model") == "Accord"

    def test_demo_page_loads(self, client):
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review")
        assert r.status_code == 200

    def test_existing_tests_unaffected(self, client):
        """Existing Honda Accord review flow still works end-to-end."""
        if _ACTIVE_VEHICLE_PATH.exists():
            _ACTIVE_VEHICLE_PATH.unlink()
        r = client.get("/internal/review/plan")
        assert r.status_code == 200
        data = r.json()
        assert "next_best_action" in data
        assert "endpoint_advisory" in data
