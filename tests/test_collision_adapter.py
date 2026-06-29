"""Tests for the CollisionDomainAdapter."""
from __future__ import annotations

import pytest

from repairgraph.adapters.collision import CollisionDomainAdapter, _default_document_roles_for_operation
from repairgraph.core.interfaces import DomainAdapter
from repairgraph.core.operational_model import DomainContext


class TestCollisionDomainAdapterProtocol:
    def test_satisfies_domain_adapter_protocol(self):
        adapter = CollisionDomainAdapter()
        assert isinstance(adapter, DomainAdapter)

    def test_domain_is_collision_repair(self):
        assert CollisionDomainAdapter().domain == "collision_repair"


class TestBuildDomainContext:
    def test_returns_domain_context(self):
        adapter = CollisionDomainAdapter(oem="Honda", year=2025, model="Accord")
        ctx = adapter.build_domain_context()
        assert isinstance(ctx, DomainContext)

    def test_domain_field(self):
        ctx = CollisionDomainAdapter().build_domain_context()
        assert ctx.domain == "collision_repair"

    def test_display_label_with_vehicle(self):
        adapter = CollisionDomainAdapter(oem="Toyota", year=2024, model="Camry", operation="quarter_panel_replacement")
        ctx = adapter.build_domain_context()
        assert "Toyota" in ctx.display_label
        assert "Camry" in ctx.display_label
        assert "2024" in ctx.display_label

    def test_context_data_has_vehicle(self):
        adapter = CollisionDomainAdapter(oem="Ford", year=2023, model="F-150")
        ctx = adapter.build_domain_context()
        assert ctx.context_data["vehicle"]["oem"] == "Ford"
        assert ctx.context_data["vehicle"]["model"] == "F-150"

    def test_context_data_has_repair(self):
        adapter = CollisionDomainAdapter(operation="sectioning", repair_area="left_rear")
        ctx = adapter.build_domain_context()
        assert ctx.context_data["repair"]["operation"] == "sectioning"
        assert ctx.context_data["repair"]["repair_area"] == "left_rear"

    def test_calibration_required_propagated(self):
        adapter = CollisionDomainAdapter(calibration_required=True)
        ctx = adapter.build_domain_context()
        assert ctx.context_data["calibration_required"] is True

    def test_corrosion_protection_propagated(self):
        adapter = CollisionDomainAdapter(corrosion_protection_required=True)
        ctx = adapter.build_domain_context()
        assert ctx.context_data["corrosion_protection_required"] is True


class TestFromRepairState:
    def test_builds_from_demo_state(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        adapter = CollisionDomainAdapter.from_repair_state(state)
        assert adapter.oem == "Honda"
        assert adapter.model == "Accord"
        assert adapter.year == 2025

    def test_extracts_material_classifications(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        adapter = CollisionDomainAdapter.from_repair_state(state)
        # Some zones should have material classifications in the Accord demo
        assert isinstance(adapter.material_classifications, dict)


class TestSourceManifestOverrides:
    def test_includes_detected_roles(self):
        adapter = CollisionDomainAdapter(operation="sectioning")
        overrides = adapter.build_source_manifest_overrides()
        assert "detected_roles" in overrides
        assert "sectioning" in overrides["detected_roles"]

    def test_calibration_operation_includes_calibration_role(self):
        adapter = CollisionDomainAdapter(operation="calibration_check")
        overrides = adapter.build_source_manifest_overrides()
        assert "calibration" in overrides["detected_roles"]


class TestDefaultDocumentRoles:
    def test_base_roles_always_present(self):
        roles = _default_document_roles_for_operation("quarter_panel_replacement")
        for role in ("repair_procedure", "welding", "corrosion_protection", "materials"):
            assert role in roles

    def test_sectioning_adds_sectioning_role(self):
        roles = _default_document_roles_for_operation("quarter_panel_sectioning")
        assert "sectioning" in roles
