"""
Collision Domain Adapter.

Translates collision repair concepts into the generic OperationalModel inputs
the RepairGraph Compiler expects.

Collision-specific concepts handled here:
  - Vehicle identification (OEM, year, model, trim)
  - Repair area and vehicle zones
  - Operation type (e.g. quarter panel replacement)
  - QA gates (calibration, corrosion protection)
  - Material classifications (steel, aluminum, AHSS)
  - Repair phases specific to collision workflow

These concepts do NOT belong in the core platform layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repairgraph.core.operational_model import DomainContext


@dataclass
class CollisionDomainAdapter:
    """Domain adapter for collision repair.

    Populates the DomainContext with vehicle and repair-specific metadata
    derived from OEM procedures, intake classification, and operator input.

    Example:
        adapter = CollisionDomainAdapter(
            oem="Honda",
            year=2025,
            model="Accord",
            operation="quarter_panel_replacement",
            repair_area="left_rear",
        )
        context = adapter.build_domain_context()
    """

    oem: str = "unknown"
    year: int | None = None
    model: str = "unknown"
    trim: str | None = None
    operation: str = "unknown"
    repair_area: str | None = None
    vehicle_systems: list[str] = field(default_factory=list)
    structural_involvement: bool = False
    calibration_required: bool = False
    corrosion_protection_required: bool = False
    material_classifications: dict[str, str] = field(default_factory=dict)
    active_zones: list[str] = field(default_factory=list)

    @property
    def domain(self) -> str:
        return "collision_repair"

    def build_domain_context(self) -> DomainContext:
        """Build a generic DomainContext from collision repair metadata."""
        display_label = self._build_display_label()
        context_data = self._build_context_data()
        return DomainContext(
            domain=self.domain,
            display_label=display_label,
            context_data=context_data,
        )

    def build_source_manifest_overrides(self) -> dict[str, Any]:
        """Supply collision-specific manifest defaults."""
        return {
            "detected_roles": _default_document_roles_for_operation(self.operation),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_display_label(self) -> str:
        parts: list[str] = []
        if self.year:
            parts.append(str(self.year))
        if self.oem and self.oem != "unknown":
            parts.append(self.oem)
        if self.model and self.model != "unknown":
            parts.append(self.model)
        if self.trim:
            parts.append(self.trim)
        label = " ".join(parts)
        if self.operation and self.operation != "unknown":
            op_label = self.operation.replace("_", " ").title()
            label = f"{label} — {op_label}" if label else op_label
        return label or "Collision Repair"

    def _build_context_data(self) -> dict[str, Any]:
        return {
            # Vehicle identification — collision concepts that don't belong in core
            "vehicle": {
                "oem": self.oem,
                "year": self.year,
                "model": self.model,
                "trim": self.trim,
            },
            # Repair scope — collision concepts
            "repair": {
                "operation": self.operation,
                "repair_area": self.repair_area,
                "active_zones": self.active_zones,
                "structural_involvement": self.structural_involvement,
            },
            # Vehicle systems requiring attention
            "vehicle_systems": self.vehicle_systems,
            # Collision-specific requirements
            "calibration_required": self.calibration_required,
            "corrosion_protection_required": self.corrosion_protection_required,
            # Material context
            "material_classifications": self.material_classifications,
        }

    @classmethod
    def from_repair_state(cls, state: Any) -> "CollisionDomainAdapter":
        """Build a CollisionDomainAdapter from an existing RepairState.

        Extracts vehicle metadata from the session and material context from
        zone activations. Used for backward-compatible integration with
        existing RepairState-based pipelines.
        """
        session = state.session
        material_classifications = {
            z.zone_id: z.material_classification
            for z in state.zones
            if z.material_classification
        }
        calibration_required = any(
            g.category == "calibration" for g in state.qa_gates
        )
        corrosion_required = any(
            b.type == "corrosion_requirement" for b in state.blockers
        )

        return cls(
            oem=getattr(session, "oem", "unknown"),
            year=getattr(session, "year", None),
            model=getattr(session, "model", "unknown"),
            operation=getattr(session, "operation", "unknown"),
            material_classifications=material_classifications,
            calibration_required=calibration_required,
            corrosion_protection_required=corrosion_required,
            active_zones=[z.zone_id for z in state.zones if z.status == "active"],
        )


def _default_document_roles_for_operation(operation: str) -> list[str]:
    """Return the expected document roles for a collision operation type."""
    base = ["repair_procedure", "welding", "corrosion_protection", "materials"]
    if "sectioning" in operation:
        base.append("sectioning")
    if "calibration" in operation or "adas" in operation.lower():
        base.append("calibration")
    if "dimension" in operation:
        base.append("dimensions")
    return base
