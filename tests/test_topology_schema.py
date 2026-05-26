import pytest
from repairgraph.topology.schema import (
    ALLOWED_SPATIAL_RELATIONSHIPS,
    ALLOWED_STRUCTURAL_TIERS,
    ALLOWED_VEHICLE_SECTIONS,
    ALLOWED_ZONE_TYPES,
    OperationRegion,
    OperationStage,
    RepairZone,
    StructuralGroup,
    TopologyGraph,
    ZoneRelationship,
)


def _evidence():
    return {
        "source_type": "normalized_procedure",
        "basis": ["test"],
        "confidence": "high",
        "requires_oem_verification": True,
        "interpretation": "advisory",
    }


# RepairZone validation

def test_valid_repair_zone():
    zone = RepairZone(
        zone_id="rear_side_outer_panel",
        label="Rear Side Outer Panel",
        zone_type="outer_panel",
        vehicle_section="rear",
        structural_tier="outer_skin",
    )
    assert zone.zone_id == "rear_side_outer_panel"
    assert zone.zone_type == "outer_panel"
    assert zone.vehicle_section == "rear"
    assert zone.structural_tier == "outer_skin"


def test_invalid_zone_type_raises():
    with pytest.raises(ValueError, match="zone_type"):
        RepairZone(
            zone_id="test",
            label="Test",
            zone_type="bumper",
            vehicle_section="rear",
            structural_tier="outer_skin",
        )


def test_invalid_vehicle_section_raises():
    with pytest.raises(ValueError, match="vehicle_section"):
        RepairZone(
            zone_id="test",
            label="Test",
            zone_type="outer_panel",
            vehicle_section="top",
            structural_tier="outer_skin",
        )


def test_invalid_structural_tier_raises():
    with pytest.raises(ValueError, match="structural_tier"):
        RepairZone(
            zone_id="test",
            label="Test",
            zone_type="outer_panel",
            vehicle_section="rear",
            structural_tier="foundation",
        )


def test_all_zone_types_accepted():
    for zt in ALLOWED_ZONE_TYPES:
        zone = RepairZone(
            zone_id=f"zone_{zt}",
            label="Test",
            zone_type=zt,
            vehicle_section="rear",
            structural_tier="unknown",
        )
        assert zone.zone_type == zt


def test_all_vehicle_sections_accepted():
    for section in ALLOWED_VEHICLE_SECTIONS:
        zone = RepairZone(
            zone_id=f"zone_{section}",
            label="Test",
            zone_type="unknown",
            vehicle_section=section,
            structural_tier="unknown",
        )
        assert zone.vehicle_section == section


def test_all_structural_tiers_accepted():
    for tier in ALLOWED_STRUCTURAL_TIERS:
        zone = RepairZone(
            zone_id=f"zone_{tier}",
            label="Test",
            zone_type="unknown",
            vehicle_section="rear",
            structural_tier=tier,
        )
        assert zone.structural_tier == tier


def test_repair_zone_material_fields_optional():
    zone = RepairZone(
        zone_id="rear_pillar_gutter",
        label="Rear Pillar Gutter",
        zone_type="gutter",
        vehicle_section="rear",
        structural_tier="inner_structure",
    )
    assert zone.material_classification is None
    assert zone.tensile_strength_mpa is None
    assert zone.source_components == []


def test_repair_zone_with_material():
    zone = RepairZone(
        zone_id="quarter_pillar_stiffener",
        label="Quarter Pillar Stiffener",
        zone_type="stiffener",
        vehicle_section="rear",
        structural_tier="reinforcement",
        material_classification="UHSS",
        tensile_strength_mpa=980,
    )
    assert zone.material_classification == "UHSS"
    assert zone.tensile_strength_mpa == 980


# ZoneRelationship validation

def test_valid_zone_relationship():
    rel = ZoneRelationship(
        source="rear_side_outer_panel",
        relationship="adjacent_to",
        target="quarter_pillar_stiffener",
        evidence=_evidence(),
    )
    assert rel.relationship == "adjacent_to"
    assert rel.source == "rear_side_outer_panel"


def test_invalid_relationship_raises():
    with pytest.raises(ValueError, match="relationship"):
        ZoneRelationship(
            source="a",
            relationship="touches",
            target="b",
        )


def test_all_spatial_relationships_accepted():
    for rel_type in ALLOWED_SPATIAL_RELATIONSHIPS:
        rel = ZoneRelationship(source="a", relationship=rel_type, target="b")
        assert rel.relationship == rel_type


def test_zone_relationship_evidence_defaults_empty():
    rel = ZoneRelationship(source="a", relationship="adjacent_to", target="b")
    assert rel.evidence == {}


# OperationRegion, StructuralGroup, OperationStage

def test_operation_region_defaults():
    region = OperationRegion(
        region_id="region_pre_repair",
        label="Pre-Repair Region",
        zone_refs=["rear_pillar_gutter"],
        applicable_operations=["inspect_if_damaged"],
    )
    assert region.sequence_phase is None
    assert region.evidence == {}


def test_structural_group_defaults():
    group = StructuralGroup(
        group_id="rear_pillar_assembly",
        label="Rear Pillar Assembly",
        group_type="pillar_assembly",
        member_zone_ids=["rear_pillar_gutter", "rear_pillar_separator"],
    )
    assert group.evidence == {}
    assert len(group.member_zone_ids) == 2


def test_operation_stage_defaults():
    stage = OperationStage(
        stage=1,
        name="pre_repair_inspection",
        label="Pre-Repair Inspection",
        zone_refs=["rear_pillar_gutter"],
        actions=[{"action": "inspect_if_damaged", "target": "rear_pillar_gutter"}],
    )
    assert stage.evidence == {}
    assert stage.stage == 1


# TopologyGraph

def test_topology_graph_assembles():
    topology = TopologyGraph(
        zones=[],
        zone_relationships=[],
        operation_regions=[],
        structural_groups=[],
        operation_stages=[],
        meta={"oem": "Honda", "model": "Accord", "year": 2025},
    )
    assert topology.meta["oem"] == "Honda"
    assert isinstance(topology.interpretation_note, str)
    assert "advisory" in topology.interpretation_note.lower()
    assert "oem" in topology.interpretation_note.lower()


def test_topology_graph_interpretation_note_present():
    topology = TopologyGraph(
        zones=[], zone_relationships=[], operation_regions=[],
        structural_groups=[], operation_stages=[], meta={},
    )
    assert len(topology.interpretation_note) > 0
