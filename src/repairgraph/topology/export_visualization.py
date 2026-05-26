from repairgraph.topology.schema import TopologyGraph


def build_zone_map(topology: TopologyGraph) -> dict:
    """
    Zone map payload: flat zone list plus zones indexed by type and vehicle section.

    Suitable as a base layer for spatial overlays or zone-selection UIs.
    All zone data is advisory and derived from normalized RepairGraph procedure data.
    """
    zones_list = []
    by_type: dict[str, list] = {}
    by_section: dict[str, list] = {}

    for zone in topology.zones:
        entry: dict = {
            "zone_id": zone.zone_id,
            "label": zone.label,
            "zone_type": zone.zone_type,
            "vehicle_section": zone.vehicle_section,
            "structural_tier": zone.structural_tier,
            "material_classification": zone.material_classification,
            "tensile_strength_mpa": zone.tensile_strength_mpa,
        }
        zones_list.append(entry)
        by_type.setdefault(zone.zone_type, []).append(entry)
        by_section.setdefault(zone.vehicle_section, []).append(entry)

    return {
        "zones": zones_list,
        "by_type": by_type,
        "by_section": by_section,
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }


def build_adjacency_graph_payload(topology: TopologyGraph) -> dict:
    """
    Visualization-ready adjacency graph: nodes, directed edges, and structural groups.

    Nodes represent repair zones. Edges encode spatial relationships from the normalized
    procedure and group membership derived from naming patterns. Suitable as input to
    graph rendering libraries (e.g., D3, Cytoscape, vis.js).
    """
    nodes = [
        {
            "id": zone.zone_id,
            "label": zone.label,
            "type": zone.zone_type,
            "section": zone.vehicle_section,
            "tier": zone.structural_tier,
            "material_classification": zone.material_classification,
            "tensile_strength_mpa": zone.tensile_strength_mpa,
        }
        for zone in topology.zones
    ]

    edges = [
        {
            "source": rel.source,
            "target": rel.target,
            "relationship": rel.relationship,
        }
        for rel in topology.zone_relationships
    ]

    # Group membership edges
    for group in topology.structural_groups:
        for member_id in group.member_zone_ids:
            edges.append({
                "source": member_id,
                "target": group.group_id,
                "relationship": "belongs_to_group",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "structural_groups": [
            {
                "group_id": g.group_id,
                "label": g.label,
                "group_type": g.group_type,
                "member_zone_ids": g.member_zone_ids,
            }
            for g in topology.structural_groups
        ],
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }


def build_operation_overlay(topology: TopologyGraph) -> dict:
    """
    Operation overlay: each zone annotated with the repair stages that touch it.

    Provides the data structure needed to color or highlight zones by operation phase,
    e.g., for step-by-step technician guidance visualizations.
    """
    zone_stage_map: dict[str, list[dict]] = {}
    for stage in topology.operation_stages:
        for ref in stage.zone_refs:
            zone_stage_map.setdefault(ref, []).append({
                "stage": stage.stage,
                "name": stage.name,
                "label": stage.label,
            })

    zone_overlays = [
        {
            "zone_id": zone.zone_id,
            "label": zone.label,
            "zone_type": zone.zone_type,
            "vehicle_section": zone.vehicle_section,
            "active_stages": zone_stage_map.get(zone.zone_id, []),
            "stage_count": len(zone_stage_map.get(zone.zone_id, [])),
        }
        for zone in topology.zones
    ]

    return {
        "zones": zone_overlays,
        "operation_stages": [
            {
                "stage": s.stage,
                "name": s.name,
                "label": s.label,
                "zone_refs": s.zone_refs,
                "action_count": len(s.actions),
            }
            for s in topology.operation_stages
        ],
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }


def build_sequence_topology(topology: TopologyGraph) -> dict:
    """
    Sequence-aware topology: each repair phase with full zone context.

    Combines the operation sequence with zone attributes (type, tier, material) to
    produce a phase-by-phase spatial narrative suitable for step guidance or validation.
    """
    zone_by_id = {z.zone_id: z for z in topology.zones}

    phases = []
    for stage in topology.operation_stages:
        zone_details = []
        for ref in stage.zone_refs:
            zone = zone_by_id.get(ref)
            if zone:
                detail: dict = {
                    "zone_id": zone.zone_id,
                    "label": zone.label,
                    "zone_type": zone.zone_type,
                    "structural_tier": zone.structural_tier,
                    "vehicle_section": zone.vehicle_section,
                }
                if zone.material_classification:
                    detail["material_classification"] = zone.material_classification
                if zone.tensile_strength_mpa:
                    detail["tensile_strength_mpa"] = zone.tensile_strength_mpa
                zone_details.append(detail)

        phases.append({
            "phase": stage.stage,
            "name": stage.name,
            "label": stage.label,
            "zones": zone_details,
            "actions": stage.actions,
            "zone_count": len(zone_details),
        })

    return {
        "phases": phases,
        "total_phases": len(phases),
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }


def build_visualization_payload(topology: TopologyGraph) -> dict:
    """
    All-in-one visualization payload combining all topology export formats.

    Contains zone_map, adjacency_graph, operation_overlay, and sequence_topology.
    This is the primary payload for downstream visualization consumers.
    """
    return {
        "zone_map": build_zone_map(topology),
        "adjacency_graph": build_adjacency_graph_payload(topology),
        "operation_overlay": build_operation_overlay(topology),
        "sequence_topology": build_sequence_topology(topology),
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }
