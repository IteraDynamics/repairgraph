"""
RepairGraph core platform layer.

Defines the canonical OperationalModel, the RepairGraph Compiler, and the
domain adapter interface. This layer is intentionally domain-agnostic.

Collision repair, aviation maintenance, industrial service, and other
procedural domains are implemented as domain adapters layered on top.
"""
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.core.interfaces import DomainAdapter
from repairgraph.core.operational_model import (
    AdvisoryNotice,
    DomainContext,
    EvidenceSummary,
    ExportLinks,
    ModelMetadata,
    OperationalModel,
    ReplaySummary,
    SourceManifest,
    WorkflowSummary,
)

__all__ = [
    "OperationalModel",
    "ModelMetadata",
    "SourceManifest",
    "DomainContext",
    "EvidenceSummary",
    "WorkflowSummary",
    "ReplaySummary",
    "ExportLinks",
    "AdvisoryNotice",
    "RepairGraphCompiler",
    "DomainAdapter",
]
