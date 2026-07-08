from dataclasses import dataclass, field

# Reference vocabulary produced by collision_zone_classifier (topology/builder.py).
# These are documentation of collision repair's zone taxonomy, not a closed
# validation set — RepairZone accepts any classifier's output (see
# __post_init__ below and docs/ARCHITECTURE_DERISK.md). A domain-specific
# ZoneClassifier is free to produce zone_type/vehicle_section/structural_tier
# values outside these sets; "unknown" remains the shared fallback meaning
# "classifier could not determine this."
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
        # Basic sanity check only — non-empty strings — not closed-set
        # validation. A pluggable ZoneClassifier (topology/builder.py) may
        # legitimately produce zone_type/vehicle_section/structural_tier
        # values outside ALLOWED_ZONE_TYPES etc.; those sets document
        # collision repair's vocabulary, they don't gate other domains'.
        for field_name, value in (
            ("zone_type", self.zone_type),
            ("vehicle_section", self.vehicle_section),
            ("structural_tier", self.structural_tier),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {value!r}")


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
