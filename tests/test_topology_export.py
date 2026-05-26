import json

import pytest
from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.topology.builder import build_topology_graph
from repairgraph.topology.export_json import topology_to_dict
from repairgraph.topology.export_mermaid import (
    build_adjacency_mermaid,
    build_operation_overlay_mermaid,
)
from repairgraph.topology.export_visualization import (
    build_adjacency_graph_payload,
    build_operation_overlay,
    build_sequence_topology,
    build_visualization_payload,
    build_zone_map,
)


@pytest.fixture
def accord_topology():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return build_topology_graph(proc, structure)


@pytest.fixture
def crv_topology():
    proc = load_procedure("Honda", 2025, "CR-V")
    structure = load_vehicle_structure("Honda", 2025, "CR-V")
    return build_topology_graph(proc, structure)


# JSON export

def test_topology_to_dict_is_serializable(accord_topology):
    d = topology_to_dict(accord_topology)
    json_str = json.dumps(d)
    assert len(json_str) > 0


def test_topology_to_dict_has_required_keys(accord_topology):
    d = topology_to_dict(accord_topology)
    for key in ("zones", "zone_relationships", "operation_regions",
                "structural_groups", "operation_stages", "meta",
                "interpretation_note"):
        assert key in d, f"Missing key: {key}"


def test_topology_to_dict_zones_nonempty(accord_topology):
    d = topology_to_dict(accord_topology)
    assert len(d["zones"]) > 0


def test_topology_to_dict_zones_have_required_fields(accord_topology):
    d = topology_to_dict(accord_topology)
    for zone in d["zones"]:
        assert "zone_id" in zone
        assert "label" in zone
        assert "zone_type" in zone
        assert "vehicle_section" in zone
        assert "structural_tier" in zone


def test_topology_to_dict_roundtrip(accord_topology):
    d = topology_to_dict(accord_topology)
    parsed = json.loads(json.dumps(d))
    assert parsed["meta"]["oem"] == "Honda"
    assert parsed["meta"]["model"] == "Accord"
    assert len(parsed["zones"]) == len(accord_topology.zones)


def test_topology_to_dict_relationships_preserve_evidence(accord_topology):
    d = topology_to_dict(accord_topology)
    for rel in d["zone_relationships"]:
        ev = rel["evidence"]
        assert "source_type" in ev
        assert "requires_oem_verification" in ev
        assert ev["requires_oem_verification"] is True


# Mermaid adjacency export

def test_adjacency_mermaid_starts_with_graph_lr(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    assert mermaid.startswith("graph LR")


def test_adjacency_mermaid_contains_zone_ids(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    for zone in accord_topology.zones:
        assert zone.zone_id in mermaid


def test_adjacency_mermaid_contains_edges(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    assert "-->" in mermaid


def test_adjacency_mermaid_has_subgraphs_for_sections(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    sections = {z.vehicle_section for z in accord_topology.zones if z.vehicle_section != "unknown"}
    for section in sections:
        assert f"sg_{section}" in mermaid


def test_adjacency_mermaid_contains_relationship_labels(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    # At least one edge label should appear
    assert "|adjacent|" in mermaid or "|joined|" in mermaid


def test_adjacency_mermaid_contains_style_directives(accord_topology):
    mermaid = build_adjacency_mermaid(accord_topology)
    assert "style " in mermaid


# Mermaid operation overlay export

def test_operation_overlay_mermaid_starts_with_graph_td(accord_topology):
    mermaid = build_operation_overlay_mermaid(accord_topology)
    assert mermaid.startswith("graph TD")


def test_operation_overlay_mermaid_has_phase_subgraphs(accord_topology):
    mermaid = build_operation_overlay_mermaid(accord_topology)
    assert "phase_" in mermaid
    assert "Phase" in mermaid


def test_operation_overlay_mermaid_has_sequence_edges(accord_topology):
    mermaid = build_operation_overlay_mermaid(accord_topology)
    assert "|seq|" in mermaid


def test_mermaid_outputs_are_strings(accord_topology):
    assert isinstance(build_adjacency_mermaid(accord_topology), str)
    assert isinstance(build_operation_overlay_mermaid(accord_topology), str)


# Zone map

def test_zone_map_structure(accord_topology):
    zm = build_zone_map(accord_topology)
    assert "zones" in zm
    assert "by_type" in zm
    assert "by_section" in zm
    assert "meta" in zm
    assert "interpretation_note" in zm


def test_zone_map_zones_nonempty(accord_topology):
    zm = build_zone_map(accord_topology)
    assert len(zm["zones"]) > 0


def test_zone_map_zones_count_matches_topology(accord_topology):
    zm = build_zone_map(accord_topology)
    assert len(zm["zones"]) == len(accord_topology.zones)


def test_zone_map_by_type_covers_all_zones(accord_topology):
    zm = build_zone_map(accord_topology)
    total_from_type = sum(len(v) for v in zm["by_type"].values())
    assert total_from_type == len(zm["zones"])


def test_zone_map_by_section_covers_all_zones(accord_topology):
    zm = build_zone_map(accord_topology)
    total_from_section = sum(len(v) for v in zm["by_section"].values())
    assert total_from_section == len(zm["zones"])


def test_zone_map_zone_fields_present(accord_topology):
    zm = build_zone_map(accord_topology)
    for z in zm["zones"]:
        assert "zone_id" in z
        assert "label" in z
        assert "zone_type" in z
        assert "vehicle_section" in z
        assert "structural_tier" in z


def test_zone_map_advisory_note(accord_topology):
    zm = build_zone_map(accord_topology)
    assert "advisory" in zm["interpretation_note"].lower()


# Adjacency graph payload

def test_adjacency_graph_payload_structure(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    assert "nodes" in payload
    assert "edges" in payload
    assert "structural_groups" in payload
    assert "meta" in payload
    assert "interpretation_note" in payload


def test_adjacency_graph_nodes_nonempty(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    assert len(payload["nodes"]) > 0


def test_adjacency_graph_nodes_count_matches(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    assert len(payload["nodes"]) == len(accord_topology.zones)


def test_adjacency_graph_edges_nonempty(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    assert len(payload["edges"]) > 0


def test_adjacency_graph_nodes_have_required_fields(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    for node in payload["nodes"]:
        assert "id" in node
        assert "label" in node
        assert "type" in node
        assert "section" in node
        assert "tier" in node


def test_adjacency_graph_includes_group_edges(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    group_edges = [e for e in payload["edges"] if e["relationship"] == "belongs_to_group"]
    assert len(group_edges) > 0


def test_adjacency_graph_serializable(accord_topology):
    payload = build_adjacency_graph_payload(accord_topology)
    json.dumps(payload)


# Operation overlay

def test_operation_overlay_structure(accord_topology):
    overlay = build_operation_overlay(accord_topology)
    assert "zones" in overlay
    assert "operation_stages" in overlay
    assert "meta" in overlay
    assert "interpretation_note" in overlay


def test_operation_overlay_zones_count_matches(accord_topology):
    overlay = build_operation_overlay(accord_topology)
    assert len(overlay["zones"]) == len(accord_topology.zones)


def test_operation_overlay_zones_have_active_stages(accord_topology):
    overlay = build_operation_overlay(accord_topology)
    total_stage_refs = sum(z["stage_count"] for z in overlay["zones"])
    assert total_stage_refs > 0


def test_operation_overlay_stage_fields_present(accord_topology):
    overlay = build_operation_overlay(accord_topology)
    for stage in overlay["operation_stages"]:
        assert "stage" in stage
        assert "name" in stage
        assert "label" in stage
        assert "zone_refs" in stage
        assert "action_count" in stage


def test_operation_overlay_zone_fields_present(accord_topology):
    overlay = build_operation_overlay(accord_topology)
    for zone in overlay["zones"]:
        assert "zone_id" in zone
        assert "label" in zone
        assert "zone_type" in zone
        assert "vehicle_section" in zone
        assert "active_stages" in zone
        assert "stage_count" in zone


# Sequence topology

def test_sequence_topology_structure(accord_topology):
    seq = build_sequence_topology(accord_topology)
    assert "phases" in seq
    assert "total_phases" in seq
    assert "meta" in seq
    assert "interpretation_note" in seq


def test_sequence_topology_phases_nonempty(accord_topology):
    seq = build_sequence_topology(accord_topology)
    assert seq["total_phases"] > 0
    assert len(seq["phases"]) == seq["total_phases"]


def test_sequence_topology_phases_have_fields(accord_topology):
    seq = build_sequence_topology(accord_topology)
    for phase in seq["phases"]:
        assert "phase" in phase
        assert "name" in phase
        assert "label" in phase
        assert "zones" in phase
        assert "actions" in phase
        assert "zone_count" in phase


def test_sequence_topology_phases_with_zones_nonempty(accord_topology):
    seq = build_sequence_topology(accord_topology)
    phases_with_zones = [p for p in seq["phases"] if p["zone_count"] > 0]
    assert len(phases_with_zones) > 0


def test_sequence_topology_zone_details_have_fields(accord_topology):
    seq = build_sequence_topology(accord_topology)
    for phase in seq["phases"]:
        for zone in phase["zones"]:
            assert "zone_id" in zone
            assert "label" in zone
            assert "zone_type" in zone
            assert "structural_tier" in zone
            assert "vehicle_section" in zone


def test_sequence_topology_uhss_zones_carry_material(accord_topology):
    seq = build_sequence_topology(accord_topology)
    all_zone_details = [z for p in seq["phases"] for z in p["zones"]]
    uhss_zones = [z for z in all_zone_details if z.get("material_classification") == "UHSS"]
    for z in uhss_zones:
        assert "tensile_strength_mpa" in z
        assert z["tensile_strength_mpa"] >= 980


# All-in-one visualization payload

def test_visualization_payload_complete(accord_topology):
    payload = build_visualization_payload(accord_topology)
    assert "zone_map" in payload
    assert "adjacency_graph" in payload
    assert "operation_overlay" in payload
    assert "sequence_topology" in payload
    assert "meta" in payload
    assert "interpretation_note" in payload


def test_visualization_payload_serializable(accord_topology):
    payload = build_visualization_payload(accord_topology)
    json_str = json.dumps(payload)
    assert len(json_str) > 100


def test_visualization_payload_advisory_notes(accord_topology):
    payload = build_visualization_payload(accord_topology)
    assert "advisory" in payload["interpretation_note"].lower()
    assert "advisory" in payload["zone_map"]["interpretation_note"].lower()
    assert "advisory" in payload["adjacency_graph"]["interpretation_note"].lower()
    assert "advisory" in payload["operation_overlay"]["interpretation_note"].lower()
    assert "advisory" in payload["sequence_topology"]["interpretation_note"].lower()


def test_visualization_payload_crv(crv_topology):
    payload = build_visualization_payload(crv_topology)
    assert payload["meta"]["model"] == "CR-V"
    assert len(payload["zone_map"]["zones"]) > 0
    assert len(payload["adjacency_graph"]["nodes"]) > 0


def test_visualization_payload_meta_consistent(accord_topology):
    payload = build_visualization_payload(accord_topology)
    assert payload["meta"]["oem"] == "Honda"
    assert payload["meta"]["model"] == "Accord"
    assert payload["meta"]["year"] == 2025
