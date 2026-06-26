"""
RepairGraph domain adapters.

Each adapter translates domain-specific concepts into the generic inputs the
RepairGraph Compiler expects. Adapters implement the DomainAdapter protocol
defined in repairgraph.core.interfaces.

Available adapters:
  - CollisionDomainAdapter: collision repair (vehicle, OEM, operation, zones)
"""
from repairgraph.adapters.collision import CollisionDomainAdapter

__all__ = ["CollisionDomainAdapter"]
