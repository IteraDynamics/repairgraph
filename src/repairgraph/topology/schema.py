from dataclasses import dataclass, field

ALLOWED_ZONE_TYPES = {
    "outer_panel",
    "inner_panel",
    "pillar",
    "rail",
    "roofline",
    "sill",
    "wheel_arch",
    "separator",
    "stiffener",
    "adapter",
    "flange",
    "gutter",
    "extension",
    "unknown",
}

ALLOWED_VEHICLE_SECTIONS = {"front", "rear", "left", "right", "center", "full", "unknown"}

ALLOWED_STRUCTURAL_TIERS = {
    "outer_skin",
    "inner_structure",
    "reinforcement",
    "substructure",
    "unknown",
}

ALLOWED_SPATIAL_RELATIONSHIPS = {
    "adjacent_to",
    "inside_zone",
    "joins_to",
    "joined_to",
    "structural_neighbor",
    "sequence_dependency",
    "belongs_to_group",
}

_INTERPRETATION_NOTE = (
    "Topology outputs are advisory structural representations derived from normalized "
    "RepairGraph data. All spatial relationships and operation regions require verification "
    "against applicable OEM procedures before operational use."
)


@dataclass
class RepairZone:
    zone_id: str
    label: str
    zone_type: str
    vehicle_section: str
    structural_tier: str
    source_components: list[str] = field(default_factory=list)
    material_classification: str | None = None
    tensile_strength_mpa: int | None = None

    def __post_init__(self):
        if self.zone_type not in ALLOWED_ZONE_TYPES:
            raise ValueError(f"Invalid zone_type: {self.zone_type!r}")
        if self.vehicle_section not in ALLOWED_VEHICLE_SECTIONS:
            raise ValueError(f"Invalid vehicle_section: {self.vehicle_section!r}")
        if self.structural_tier not in ALLOWED_STRUCTURAL_TIERS:
            raise ValueError(f"Invalid structural_tier: {self.structural_tier!r}")


@dataclass
class ZoneRelationship:
    source: str
    relationship: str
    target: str
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.relationship not in ALLOWED_SPATIAL_RELATIONSHIPS:
            raise ValueError(f"Invalid relationship: {self.relationship!r}")


@dataclass
class OperationRegion:
    region_id: str
    label: str
    zone_refs: list[str]
    applicable_operations: list[str]
    sequence_phase: int | None = None
    evidence: dict = field(default_factory=dict)


@dataclass
class StructuralGroup:
    group_id: str
    label: str
    group_type: str
    member_zone_ids: list[str]
    evidence: dict = field(default_factory=dict)


@dataclass
class OperationStage:
    stage: int
    name: str
    label: str
    zone_refs: list[str]
    actions: list[dict]
    evidence: dict = field(default_factory=dict)


@dataclass
class TopologyGraph:
    zones: list[RepairZone]
    zone_relationships: list[ZoneRelationship]
    operation_regions: list[OperationRegion]
    structural_groups: list[StructuralGroup]
    operation_stages: list[OperationStage]
    meta: dict
    interpretation_note: str = field(default=_INTERPRETATION_NOTE)
