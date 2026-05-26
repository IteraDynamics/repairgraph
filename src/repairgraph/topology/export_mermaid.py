from repairgraph.topology.schema import TopologyGraph

_RELATIONSHIP_LABEL = {
    "adjacent_to": "adjacent",
    "joined_to": "joined",
    "joins_to": "joins",
    "inside_zone": "inside",
    "structural_neighbor": "neighbor",
    "sequence_dependency": "seq",
    "belongs_to_group": "group",
}

_ZONE_TYPE_STYLE = {
    "outer_panel": "fill:#b3d9ff,stroke:#2266aa",
    "inner_panel": "fill:#d4edda,stroke:#28a745",
    "pillar": "fill:#fff3cd,stroke:#ffc107",
    "rail": "fill:#fce8e8,stroke:#dc3545",
    "stiffener": "fill:#e8d5f5,stroke:#6f42c1",
    "separator": "fill:#d6eaf8,stroke:#2e86c1",
    "gutter": "fill:#d5f5e3,stroke:#1e8449",
    "sill": "fill:#fdebd0,stroke:#e67e22",
    "roofline": "fill:#eaecee,stroke:#7f8c8d",
    "wheel_arch": "fill:#f9e4b7,stroke:#d4ac0d",
    "adapter": "fill:#fadbd8,stroke:#e74c3c",
    "flange": "fill:#d7dbdd,stroke:#566573",
    "extension": "fill:#ebf5fb,stroke:#1a5276",
    "unknown": "fill:#f8f9fa,stroke:#adb5bd",
}


def _safe_label(text: str) -> str:
    return text.replace('"', "'").replace("[", "(").replace("]", ")")


def build_adjacency_mermaid(topology: TopologyGraph) -> str:
    """
    Mermaid diagram of zone adjacency relationships grouped by vehicle section.

    Zones with known vehicle sections appear in named subgraphs. Spatial relationships
    from the normalized procedure are rendered as directed edges.
    """
    lines = ["graph LR"]

    by_section: dict[str, list] = {}
    for zone in topology.zones:
        by_section.setdefault(zone.vehicle_section, []).append(zone)

    # Emit subgraphs for known sections
    for section in ("front", "rear", "center", "left", "right", "full"):
        section_zones = by_section.get(section, [])
        if not section_zones:
            continue
        lines.append(f"  subgraph sg_{section}[{section.title()} Section]")
        for zone in section_zones:
            label = _safe_label(zone.label)
            lines.append(f'    {zone.zone_id}["{label}"]')
        lines.append("  end")

    # Unknown-section zones outside any subgraph
    for zone in by_section.get("unknown", []):
        label = _safe_label(zone.label)
        lines.append(f'  {zone.zone_id}["{label}"]')

    lines.append("")

    # Spatial relationship edges
    for rel in topology.zone_relationships:
        edge_label = _RELATIONSHIP_LABEL.get(rel.relationship, rel.relationship)
        lines.append(f"  {rel.source} -->|{edge_label}| {rel.target}")

    # Style nodes by zone type
    lines.append("")
    for zone in topology.zones:
        style = _ZONE_TYPE_STYLE.get(zone.zone_type, _ZONE_TYPE_STYLE["unknown"])
        lines.append(f"  style {zone.zone_id} {style}")

    return "\n".join(lines) + "\n"


def build_operation_overlay_mermaid(topology: TopologyGraph) -> str:
    """
    Mermaid diagram with operation stages as subgraphs containing their zone references.

    Each repair phase is rendered as a named subgraph. Sequence dependencies between
    consecutive phases are rendered as edges between the first node in each phase.
    """
    lines = ["graph TD"]

    for stage in topology.operation_stages:
        if not stage.zone_refs:
            continue
        safe_label = _safe_label(stage.label)
        lines.append(f"  subgraph phase_{stage.stage}[Phase {stage.stage}: {safe_label}]")
        for ref in stage.zone_refs[:6]:  # cap to avoid massive diagrams
            label = _safe_label(ref.replace("_", " "))
            lines.append(f'    {ref}_p{stage.stage}["{label}"]')
        lines.append("  end")

    lines.append("")

    # Sequence dependency edges between phases
    stages_with_refs = [s for s in topology.operation_stages if s.zone_refs]
    for i in range(1, len(stages_with_refs)):
        prev = stages_with_refs[i - 1]
        curr = stages_with_refs[i]
        src = f"{prev.zone_refs[0]}_p{prev.stage}"
        tgt = f"{curr.zone_refs[0]}_p{curr.stage}"
        lines.append(f"  {src} -->|seq| {tgt}")

    return "\n".join(lines) + "\n"
