import pytest
from repairgraph.query.loader import load_all_procedures, load_procedure, load_vehicle_structure
from repairgraph.topology.builder import _classify_zone, build_topology_graph
from repairgraph.topology.schema import TopologyGraph


# Build returns correct type

def test_build_returns_topology_graph():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)
    assert isinstance(topology, TopologyGraph)


def test_build_without_structure():
    proc = load_procedure("Honda", 2025, "Civic")
    topology = build_topology_graph(proc)
    assert isinstance(topology, TopologyGraph)
    assert len(topology.zones) > 0


# Zone collection

def test_zones_nonempty():
    proc = load_procedure("Honda", 2025, "CR-V")
    topology = build_topology_graph(proc)
    assert len(topology.zones) > 0


def test_zones_include_spatial_relationship_endpoints():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    zone_ids = {z.zone_id for z in topology.zones}

    for rel in proc.get("spatial_relationships", []):
        assert rel["source"] in zone_ids, f"Source {rel['source']} missing from zones"
        assert rel["target"] in zone_ids, f"Target {rel['target']} missing from zones"


def test_zones_include_dependency_targets():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    zone_ids = {z.zone_id for z in topology.zones}

    for dep in proc.get("dependencies", []):
        assert dep["target"] in zone_ids, f"Dependency {dep['target']} missing from zones"


def test_zones_include_structure_nodes():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)
    zone_ids = {z.zone_id for z in topology.zones}

    for node in structure.get("structure_nodes", []):
        assert node in zone_ids, f"Structure node {node} missing from zones"


def test_zones_include_material_components():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)
    zone_ids = {z.zone_id for z in topology.zones}

    for mat in structure.get("materials", []):
        assert mat["component"] in zone_ids


def test_zones_include_sectioning_locations():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    zone_ids = {z.zone_id for z in topology.zones}

    for loc in proc.get("sectioning_locations", []):
        assert loc["zone"] in zone_ids


# Zone classification

def test_classify_outer_panel():
    zt, vs, st = _classify_zone("rear_side_outer_panel")
    assert zt == "outer_panel"
    assert vs == "rear"
    assert st == "outer_skin"


def test_classify_stiffener_before_pillar():
    zt, vs, st = _classify_zone("quarter_pillar_stiffener")
    assert zt == "stiffener"
    assert st == "reinforcement"


def test_classify_rail():
    zt, vs, st = _classify_zone("rear_roof_rail_upper")
    assert zt == "rail"
    assert vs == "rear"
    assert st == "substructure"


def test_classify_gutter():
    zt, vs, st = _classify_zone("rear_pillar_gutter")
    assert zt == "gutter"
    assert vs == "rear"
    assert st == "inner_structure"


def test_classify_separator():
    zt, vs, st = _classify_zone("wheel_arch_separator")
    assert zt == "separator"
    assert st == "reinforcement"


def test_classify_inner_panel():
    zt, vs, st = _classify_zone("rear_inner_panel")
    assert zt == "inner_panel"
    assert vs == "rear"
    assert st == "inner_structure"


def test_classify_roofline():
    zt, vs, st = _classify_zone("roof_panel")
    assert zt == "roofline"
    assert vs == "center"
    assert st == "outer_skin"


def test_classify_pillar():
    zt, vs, st = _classify_zone("rear_pillar_inner")
    assert zt == "pillar"
    assert vs == "rear"
    assert st == "substructure"


def test_classify_adapter():
    zt, vs, st = _classify_zone("rear_combination_adapter")
    assert zt == "adapter"
    assert vs == "rear"
    assert st == "reinforcement"


def test_classify_flange():
    zt, vs, st = _classify_zone("side_sill_extension_end_flange")
    assert zt == "flange"


def test_classify_extension():
    zt, vs, st = _classify_zone("wheel_arch_lower_extension")
    assert zt == "extension"


def test_classify_sill():
    zt, vs, st = _classify_zone("side_sill_panel")
    assert zt == "sill"
    assert st == "substructure"


# Zone material data

def test_uhss_zone_carries_material_data():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)

    uhss_zones = [z for z in topology.zones if z.material_classification == "UHSS"]
    assert len(uhss_zones) > 0
    for zone in uhss_zones:
        assert zone.tensile_strength_mpa is not None
        assert zone.tensile_strength_mpa >= 980


# Zone relationships

def test_zone_relationships_nonempty():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    assert len(topology.zone_relationships) > 0


def test_zone_relationships_match_procedure():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    rel_pairs = {(r.source, r.target) for r in topology.zone_relationships}
    for rel in proc.get("spatial_relationships", []):
        assert (rel["source"], rel["target"]) in rel_pairs


def test_all_zone_relationships_have_valid_evidence():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    for rel in topology.zone_relationships:
        ev = rel.evidence
        assert "source_type" in ev
        assert "basis" in ev
        assert "confidence" in ev
        assert "requires_oem_verification" in ev
        assert ev["requires_oem_verification"] is True
        assert "interpretation" in ev


def test_zone_relationships_use_allowed_types():
    from repairgraph.topology.schema import ALLOWED_SPATIAL_RELATIONSHIPS

    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    for rel in topology.zone_relationships:
        assert rel.relationship in ALLOWED_SPATIAL_RELATIONSHIPS


# Structural groups

def test_structural_groups_inferred_for_accord():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)
    assert len(topology.structural_groups) > 0


def test_structural_groups_have_multiple_members():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)

    for group in topology.structural_groups:
        assert len(group.member_zone_ids) >= 2, (
            f"Group {group.group_id} has fewer than 2 members"
        )


def test_structural_groups_have_evidence():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)

    for group in topology.structural_groups:
        assert "source_type" in group.evidence
        assert group.evidence["requires_oem_verification"] is True


def test_rear_pillar_assembly_present_for_accord():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)

    group_ids = {g.group_id for g in topology.structural_groups}
    assert "rear_pillar_assembly" in group_ids


def test_rear_combination_assembly_present_for_accord():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc, structure)

    group_ids = {g.group_id for g in topology.structural_groups}
    assert "rear_combination_assembly" in group_ids


# Operation stages

def test_operation_stages_nonempty():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    assert len(topology.operation_stages) > 0


def test_operation_stages_have_evidence():
    proc = load_procedure("Honda", 2025, "CR-V")
    topology = build_topology_graph(proc)

    for stage in topology.operation_stages:
        assert "source_type" in stage.evidence
        assert stage.evidence["requires_oem_verification"] is True


def test_operation_stages_sequential():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    stage_numbers = [s.stage for s in topology.operation_stages]
    assert stage_numbers == sorted(stage_numbers)
    assert stage_numbers[0] >= 1


def test_operation_stages_have_named_phases():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    names = {s.name for s in topology.operation_stages}
    assert "panel_installation_and_joining" in names


# Operation regions

def test_operation_regions_nonempty():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    assert len(topology.operation_regions) > 0


def test_operation_regions_have_evidence():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)

    for region in topology.operation_regions:
        assert "source_type" in region.evidence
        assert region.evidence["requires_oem_verification"] is True


def test_full_coverage_regions_reference_zones():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    zone_ids = {z.zone_id for z in topology.zones}

    # panel_installation_and_joining has no specific zone_refs from items
    # so it should fall back to all zones
    joining_region = next(
        (r for r in topology.operation_regions if "installation" in r.region_id),
        None,
    )
    if joining_region:
        assert len(joining_region.zone_refs) > 0
        for ref in joining_region.zone_refs:
            assert ref in zone_ids


# Meta

def test_meta_fields_populated():
    proc = load_procedure("Honda", 2025, "Pilot")
    topology = build_topology_graph(proc)
    assert topology.meta["oem"] == "Honda"
    assert topology.meta["model"] == "Pilot"
    assert topology.meta["year"] == 2025
    assert topology.meta["zone_count"] == len(topology.zones)
    assert topology.meta["relationship_count"] == len(topology.zone_relationships)
    assert topology.meta["group_count"] == len(topology.structural_groups)
    assert topology.meta["stage_count"] == len(topology.operation_stages)


# Cross-model

def test_topology_builds_for_all_models():
    for proc in load_all_procedures():
        # Skip intake-derived procedures — they have empty spatial_relationships
        # by design (we don't fabricate zone topology from classification evidence).
        source = proc.get("source", {})
        if isinstance(source, dict) and source.get("intake_id"):
            continue
        topology = build_topology_graph(proc)
        assert isinstance(topology, TopologyGraph)
        assert len(topology.zones) > 0
        assert topology.meta["oem"] == proc.get("oem")
        assert topology.meta["model"] == proc.get("model")


# Trust semantics

def test_interpretation_note_is_advisory():
    proc = load_procedure("Honda", 2025, "Accord")
    topology = build_topology_graph(proc)
    note = topology.interpretation_note.lower()
    assert "advisory" in note
    assert "oem" in note
    assert "verification" in note
