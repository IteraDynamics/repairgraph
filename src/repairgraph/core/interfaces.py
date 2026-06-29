"""
Domain adapter interface for the RepairGraph Compiler.

Domain adapters translate domain-specific concepts into the generic
OperationalModel. They are responsible for populating domain_context
and providing any domain-specific compilation inputs.

Examples:
  - CollisionDomainAdapter: vehicle, OEM, repair area, calibration
  - AviationAdapter: aircraft type, ATA chapter, task card
  - IndustrialAdapter: equipment model, service interval, component
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from repairgraph.core.operational_model import DomainContext


@runtime_checkable
class DomainAdapter(Protocol):
    """Protocol that all domain adapters must satisfy.

    A domain adapter is responsible for translating domain-specific input
    into the generic types the RepairGraph Compiler consumes. The adapter
    does NOT contain compilation logic—it supplies context and inputs.
    """

    @property
    def domain(self) -> str:
        """Stable identifier for this domain (e.g. 'collision_repair')."""
        ...

    def build_domain_context(self) -> DomainContext:
        """Return a DomainContext populated with domain-specific metadata."""
        ...

    def build_source_manifest_overrides(self) -> dict[str, Any]:
        """Return any domain-specific source manifest fields to merge."""
        ...
