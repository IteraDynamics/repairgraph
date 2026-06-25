"""
Tests for topology layout definitions.
"""
import pytest

from repairgraph.viewer.topology_layout import (
    ACTION_STATUS_COLORS,
    PHASE_STATUS_COLORS,
    QA_STATUS_COLORS,
    VEHICLE_REGIONS,
    ZONE_STATUS_COLORS,
)


class TestVehicleRegions:
    def test_at_least_ten_regions(self):
        assert len(VEHICLE_REGIONS) >= 10

    def test_each_region_has_required_fields(self):
        for reg in VEHICLE_REGIONS:
            assert "id" in reg, f"Missing id in {reg}"
            assert "label" in reg
            assert "zone_keys" in reg
            assert "shape" in reg
            assert "x" in reg
            assert "y" in reg
            assert "width" in reg
            assert "height" in reg
            assert "cx" in reg
            assert "cy" in reg

    def test_ids_are_unique(self):
        ids = [r["id"] for r in VEHICLE_REGIONS]
        assert len(ids) == len(set(ids))

    def test_ids_prefixed_region(self):
        for reg in VEHICLE_REGIONS:
            assert reg["id"].startswith("region_"), f"Bad id prefix: {reg['id']}"

    def test_zone_keys_non_empty(self):
        for reg in VEHICLE_REGIONS:
            assert len(reg["zone_keys"]) > 0, f"Empty zone_keys for {reg['id']}"

    def test_shapes_are_rect(self):
        for reg in VEHICLE_REGIONS:
            assert reg["shape"] in {"rect", "path", "ellipse"}

    def test_dimensions_positive(self):
        for reg in VEHICLE_REGIONS:
            assert reg["width"] > 0
            assert reg["height"] > 0


class TestZoneStatusColors:
    def test_all_zone_statuses_covered(self):
        required = {"inactive", "pending", "active", "complete", "blocked"}
        assert required.issubset(set(ZONE_STATUS_COLORS.keys()))

    def test_each_color_has_fill_stroke_label(self):
        for status, color in ZONE_STATUS_COLORS.items():
            assert "fill" in color, f"Missing fill for {status}"
            assert "stroke" in color, f"Missing stroke for {status}"
            assert "label" in color, f"Missing label for {status}"

    def test_colors_are_hex(self):
        for status, color in ZONE_STATUS_COLORS.items():
            assert color["fill"].startswith("#"), f"fill not hex for {status}"
            assert color["stroke"].startswith("#"), f"stroke not hex for {status}"


class TestActionStatusColors:
    def test_common_statuses_present(self):
        required = {"pending", "in_progress", "complete", "blocked"}
        assert required.issubset(set(ACTION_STATUS_COLORS.keys()))

    def test_colors_are_hex(self):
        for status, color in ACTION_STATUS_COLORS.items():
            assert color.startswith("#"), f"color not hex for {status}"


class TestQAStatusColors:
    def test_common_statuses_present(self):
        required = {"open", "passed", "failed"}
        assert required.issubset(set(QA_STATUS_COLORS.keys()))


class TestPhaseStatusColors:
    def test_common_statuses_present(self):
        required = {"not_started", "in_progress", "complete", "blocked"}
        assert required.issubset(set(PHASE_STATUS_COLORS.keys()))
