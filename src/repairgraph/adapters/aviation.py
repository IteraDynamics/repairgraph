"""
Aviation Maintenance Domain Adapter.

Exists to stress-test the DomainAdapter protocol and the "domain-agnostic
core" claim in operational_model.py, not as a product. Translates aviation
maintenance concepts (task cards, ATA chapters, airworthiness) into the
generic OperationalModel inputs the RepairGraph Compiler already expects for
collision repair — with no changes to the compiler.

Aviation-specific concepts handled here:
  - Aircraft identification (type, registration/tail number)
  - Task card and ATA chapter (the aviation equivalent of an OEM procedure
    and repair area)
  - Airworthiness directive references
  - Inspection interval / maintenance check type

These concepts do NOT belong in the core platform layer — same rule as
CollisionDomainAdapter. See docs/ARCHITECTURE_DERISK.md for what this
stress test proved and what it found still coupled to collision repair.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repairgraph.core.operational_model import DomainContext


@dataclass
class AviationDomainAdapter:
    """Domain adapter for aviation maintenance.

    Populates the DomainContext with aircraft and task-card metadata, the
    aviation equivalent of vehicle + OEM procedure metadata in collision
    repair.

    Example:
        adapter = AviationDomainAdapter(
            aircraft_type="A320-200",
            registration="N12345",
            ata_chapter="32",
            ata_chapter_label="Landing Gear",
            task_card_id="TC-32-11-04",
            check_type="100-hour",
        )
        context = adapter.build_domain_context()
    """

    aircraft_type: str = "unknown"
    registration: str | None = None
    ata_chapter: str = "unknown"
    ata_chapter_label: str = ""
    task_card_id: str = "unknown"
    check_type: str = "unknown"
    airworthiness_directives: list[str] = field(default_factory=list)
    systems_affected: list[str] = field(default_factory=list)
    return_to_service_required: bool = True
    inspector_sign_off_required: bool = False

    @property
    def domain(self) -> str:
        return "aviation_maintenance"

    def build_domain_context(self) -> DomainContext:
        """Build a generic DomainContext from aviation maintenance metadata."""
        return DomainContext(
            domain=self.domain,
            display_label=self._build_display_label(),
            context_data=self._build_context_data(),
        )

    def build_source_manifest_overrides(self) -> dict[str, Any]:
        """Supply aviation-specific manifest defaults."""
        return {
            "detected_roles": _default_document_roles_for_check(self.check_type),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_display_label(self) -> str:
        parts: list[str] = []
        if self.aircraft_type and self.aircraft_type != "unknown":
            parts.append(self.aircraft_type)
        if self.registration:
            parts.append(self.registration)
        label = " ".join(parts)
        if self.task_card_id and self.task_card_id != "unknown":
            label = f"{label} — {self.task_card_id}" if label else self.task_card_id
        return label or "Aviation Maintenance"

    def _build_context_data(self) -> dict[str, Any]:
        return {
            "aircraft": {
                "aircraft_type": self.aircraft_type,
                "registration": self.registration,
            },
            "task": {
                "task_card_id": self.task_card_id,
                "ata_chapter": self.ata_chapter,
                "ata_chapter_label": self.ata_chapter_label,
                "check_type": self.check_type,
                "systems_affected": self.systems_affected,
            },
            "airworthiness_directives": self.airworthiness_directives,
            "return_to_service_required": self.return_to_service_required,
            "inspector_sign_off_required": self.inspector_sign_off_required,
        }

    @classmethod
    def from_repair_state(cls, state: Any) -> "AviationDomainAdapter":
        """Build an AviationDomainAdapter from an existing RepairState.

        Mirrors CollisionDomainAdapter.from_repair_state — proves the same
        reconstruction pattern generalizes. Reads the session through its
        domain-neutral primary_context/secondary_context/context_label
        properties (state/schema.py) rather than the collision-named
        oem/model/operation fields directly.
        """
        session = state.session
        inspector_required = any(
            g.category == "airworthiness" for g in state.qa_gates
        )
        return cls(
            aircraft_type=session.primary_context or "unknown",
            registration=session.secondary_context or None,
            task_card_id=session.context_label or "unknown",
            inspector_sign_off_required=inspector_required,
            systems_affected=[z.zone_id for z in state.zones if z.status == "active"],
        )


def _default_document_roles_for_check(check_type: str) -> list[str]:
    """Return the expected document roles for an aviation check type."""
    base = ["task_card", "inspection_procedure"]
    if "100" in check_type or "annual" in check_type.lower():
        base.append("airworthiness_directive")
    if "engine" in check_type.lower():
        base.append("engine_manual")
    return base
