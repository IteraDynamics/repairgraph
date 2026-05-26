from collections import defaultdict

from repairgraph.evidence import build_evidence
from repairgraph.inference.sequencing import build_operation_sequence
from repairgraph.topology.schema import (
    ALLOWED_SPATIAL_RELATIONSHIPS,
    OperationRegion,
    OperationStage,
    RepairZone,
    StructuralGroup,
    TopologyGraph,
    ZoneRelationship,
)

_TIER_BY_ZONE_TYPE = {
    "outer_panel": "outer_skin",
    "roofline": "outer_skin",
    "inner_panel": "inner_structure",
    "gutter": "inner_structure",
    "pillar": "substructure",
    "rail": "substructure",
    "sill": "substructure",
    "stiffener": "reinforcement",
    "separator": "reinforcement",
    "adapter": "reinforcement",
    "wheel_arch": "reinforcement",
    "flange": "reinforcement",
    "extension": "reinforcement",
}

_GROUP_TYPE_BY_KEYWORD = {
    "pillar": "pillar_assembly",
    "rail": "rail_assembly",
    "adapter": "adapter_group",
    "panel": "panel_group",
    "separator": "separator_group",
    "stiffener": "stiffener_group",
    "gutter": "gutter_group",
}


def _classify_zone(zone_id: str) -> tuple[str, str, str]:
    """Return (zone_type, vehicle_section, structural_tier) for a canonical zone_id."""
    name = zone_id.lower()

    # Check specific composite terms before generic structural terms
    if "stiffener" in name or "reinforcement" in name:
        zone_type = "stiffener"
    elif "separator" in name:
        zone_type = "separator"
    elif "gutter" in name:
        zone_type = "gutter"
    elif "adapter" in name:
        zone_type = "adapter"
    elif "flange" in name:
        zone_type = "flange"
    elif "extension" in name:
        zone_type = "extension"
    elif "wheel_arch" in name:
        zone_type = "wheel_arch"
    elif "sill" in name:
        zone_type = "sill"
    elif "rail" in name:
        zone_type = "rail"
    elif "roof" in name:
        zone_type = "roofline"
    elif "pillar" in name:
        zone_type = "pillar"
    elif "outer" in name and "panel" in name:
        zone_type = "outer_panel"
    elif "inner" in name:
        zone_type = "inner_panel"
    elif "panel" in name:
        zone_type = "outer_panel"
    else:
        zone_type = "unknown"

    if "front" in name:
        vehicle_section = "front"
    elif "rear" in name:
        vehicle_section = "rear"
    elif "roof" in name:
        vehicle_section = "center"
    else:
        vehicle_section = "unknown"

    structural_tier = _TIER_BY_ZONE_TYPE.get(zone_type, "unknown")

    return zone_type, vehicle_section, structural_tier


def _collect_zone_ids(procedure: dict, structure: dict | None) -> set[str]:
    zone_ids: set[str] = set()

    for rel in procedure.get("spatial_relationships", []):
        zone_ids.add(rel["source"])
        zone_ids.add(rel["target"])

    for dep in procedure.get("dependencies", []):
        zone_ids.add(dep["target"])

    for loc in procedure.get("sectioning_locations", []):
        zone_ids.add(loc["zone"])

    if structure:
        zone_ids.update(structure.get("structure_nodes", []))
        for mat in structure.get("materials", []):
            zone_ids.add(mat["component"])

    return zone_ids


def _build_zones(procedure: dict, structure: dict | None) -> list[RepairZone]:
    zone_ids = _collect_zone_ids(procedure, structure)

    material_map: dict[str, dict] = {}
    if structure:
        for mat in structure.get("materials", []):
            material_map[mat["component"]] = mat

    zones = []
    for zid in sorted(zone_ids):
        zone_type, vehicle_section, structural_tier = _classify_zone(zid)
        mat = material_map.get(zid)

        zones.append(RepairZone(
            zone_id=zid,
            label=zid.replace("_", " "),
            zone_type=zone_type,
            vehicle_section=vehicle_section,
            structural_tier=structural_tier,
            source_components=[zid],
            material_classification=mat.get("classification") if mat else None,
            tensile_strength_mpa=mat.get("tensile_strength_mpa") if mat else None,
        ))

    return zones


def _normalize_relationship(raw: str) -> str:
    if raw in ALLOWED_SPATIAL_RELATIONSHIPS:
        return raw
    if raw in ("joins_to", "joined_to"):
        return "joined_to"
    return "adjacent_to"


def _build_zone_relationships(procedure: dict) -> list[ZoneRelationship]:
    relationships = []

    for rel in procedure.get("spatial_relationships", []):
        relationship = _normalize_relationship(rel["relationship"])
        evidence = build_evidence(
            source_type="normalized_procedure",
            basis=["spatial_relationship_declared", rel["relationship"]],
            confidence="high",
            interpretation="normalized_fact",
        )
        relationships.append(ZoneRelationship(
            source=rel["source"],
            relationship=relationship,
            target=rel["target"],
            evidence=evidence,
        ))

    return relationships


def _infer_group_type(prefix: str) -> str:
    for keyword, group_type in _GROUP_TYPE_BY_KEYWORD.items():
        if keyword in prefix:
            return group_type
    return "structural_group"


def _infer_structural_groups(zones: list[RepairZone]) -> list[StructuralGroup]:
    prefix_map: dict[str, list[str]] = defaultdict(list)

    for zone in zones:
        tokens = zone.zone_id.split("_")
        if len(tokens) >= 3:
            prefix = "_".join(tokens[:2])
            prefix_map[prefix].append(zone.zone_id)

    groups = []
    for prefix, members in sorted(prefix_map.items()):
        if len(members) >= 2:
            evidence = build_evidence(
                source_type="graph_relationship",
                basis=["structural_prefix_grouping", prefix],
                confidence="medium",
                interpretation="graph_relationship",
            )
            groups.append(StructuralGroup(
                group_id=f"{prefix}_assembly",
                label=prefix.replace("_", " ").title() + " Assembly",
                group_type=_infer_group_type(prefix),
                member_zone_ids=sorted(members),
                evidence=evidence,
            ))

    return groups


def _extract_zone_refs(items: list[dict]) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for item in items:
        ref = item.get("target") or item.get("zone")
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _build_operation_stages(procedure: dict) -> list[OperationStage]:
    seq = build_operation_sequence(procedure)
    stages = []

    for phase in seq["phases"]:
        zone_refs = _extract_zone_refs(phase.get("items", []))
        evidence = build_evidence(
            source_type="normalized_procedure",
            basis=["operation_sequence_phase", phase["name"]],
            confidence="medium",
            interpretation="advisory",
        )
        stages.append(OperationStage(
            stage=phase["phase"],
            name=phase["name"],
            label=phase["label"],
            zone_refs=zone_refs,
            actions=phase.get("items", []),
            evidence=evidence,
        ))

    return stages


def _build_operation_regions(
    zones: list[RepairZone],
    stages: list[OperationStage],
) -> list[OperationRegion]:
    zone_ids = {z.zone_id for z in zones}

    # Phases that cover the full zone set when no specific refs are found
    _full_coverage_phases = {
        "panel_installation_and_joining",
        "corrosion_protection",
        "post_repair_verification",
    }

    regions = []
    for stage in stages:
        valid_refs = [ref for ref in stage.zone_refs if ref in zone_ids]

        if not valid_refs and stage.name in _full_coverage_phases:
            valid_refs = sorted(zone_ids)

        evidence = build_evidence(
            source_type="normalized_procedure",
            basis=["operation_region_mapped", stage.name],
            confidence="medium",
            interpretation="advisory",
        )
        regions.append(OperationRegion(
            region_id=f"region_{stage.name}",
            label=f"{stage.label} Region",
            zone_refs=valid_refs,
            applicable_operations=[a.get("action", "") for a in stage.actions],
            sequence_phase=stage.stage,
            evidence=evidence,
        ))

    return regions


def build_topology_graph(procedure: dict, structure: dict | None = None) -> TopologyGraph:
    """
    Build a spatial topology graph from a normalized procedure and optional structure.

    Zones are collected from spatial_relationships, dependencies, sectioning locations,
    structure_nodes, and material components. Structural groups are inferred from shared
    naming prefixes. Operation stages and regions map the repair sequence to spatial context.

    All outputs are advisory and require OEM verification.
    """
    zones = _build_zones(procedure, structure)
    zone_relationships = _build_zone_relationships(procedure)
    structural_groups = _infer_structural_groups(zones)
    operation_stages = _build_operation_stages(procedure)
    operation_regions = _build_operation_regions(zones, operation_stages)

    return TopologyGraph(
        zones=zones,
        zone_relationships=zone_relationships,
        operation_regions=operation_regions,
        structural_groups=structural_groups,
        operation_stages=operation_stages,
        meta={
            "oem": procedure.get("oem"),
            "year": procedure.get("year"),
            "model": procedure.get("model"),
            "operation": procedure.get("operation"),
            "zone_count": len(zones),
            "relationship_count": len(zone_relationships),
            "group_count": len(structural_groups),
            "stage_count": len(operation_stages),
        },
    )
