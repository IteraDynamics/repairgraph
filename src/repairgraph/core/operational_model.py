"""
Canonical OperationalModel produced by the RepairGraph Compiler.

The OperationalModel is the stable internal artifact that downstream consumers
(viewers, reports, APIs, insights) should project from. It is intentionally
domain-agnostic. Collision-specific concepts live in domain adapters.

All outputs are advisory. See AdvisoryNotice for the machine-readable posture.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from repairgraph.insights.schema import InsightPayload
from repairgraph.state.schema import RepairState
from repairgraph.topology.schema import TopologyGraph

_SCHEMA_VERSION = "1.0.0"
_GENERATED_BY = "repairgraph.core.compiler"


@dataclass
class ModelMetadata:
    """Identity and provenance of a compiled OperationalModel."""
    model_id: str
    schema_name: str
    schema_version: str
    generated_at: str
    generated_by: str
    compiler_version: str
    advisory: bool = True

    @classmethod
    def create(cls, *, compiler_version: str = "1.0.0") -> "ModelMetadata":
        return cls(
            model_id=str(uuid.uuid4()),
            schema_name="repairgraph.core.operational_model",
            schema_version=_SCHEMA_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by=_GENERATED_BY,
            compiler_version=compiler_version,
            advisory=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "generated_by": self.generated_by,
            "compiler_version": self.compiler_version,
            "advisory": self.advisory,
        }


@dataclass
class SourceManifest:
    """Summary of customer-supplied source material.

    Preserves auditability without retaining source documents.
    """
    source_count: int = 0
    filenames: list[str] = field(default_factory=list)
    detected_roles: list[str] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)
    readiness: str = "incomplete"
    extraction_warnings: list[str] = field(default_factory=list)
    customer_owned_content_notice: str = (
        "Source documents are customer-owned OEM repair information. "
        "RepairGraph processes this content but does not claim ownership or "
        "distribute it. Derived outputs are the RepairGraph operational artifact."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "filenames": self.filenames,
            "detected_roles": self.detected_roles,
            "missing_roles": self.missing_roles,
            "readiness": self.readiness,
            "extraction_warnings": self.extraction_warnings,
            "customer_owned_content_notice": self.customer_owned_content_notice,
        }


@dataclass
class DomainContext:
    """Domain-specific context for a compiled OperationalModel.

    The OperationalModel is domain-agnostic. Domain adapters populate this
    section with structured, domain-specific metadata. Examples:

      - collision_repair: vehicle, OEM, operation, repair area
      - aviation_maintenance: aircraft type, ATA chapter, task card
      - industrial_service: equipment model, service interval, component
    """
    domain: str
    display_label: str = ""
    context_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "display_label": self.display_label,
            "context_data": self.context_data,
        }


@dataclass
class EvidenceSummary:
    """Minimal explainable evidence carried forward from source classification.

    Evidence items explain why RepairGraph reached a conclusion.
    They reference source identifiers and document roles rather than
    reproducing source document content.
    """
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    confidence_by_category: dict[str, float] = field(default_factory=dict)
    requires_oem_verification: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_items": self.evidence_items,
            "confidence_by_category": self.confidence_by_category,
            "requires_oem_verification": self.requires_oem_verification,
        }


@dataclass
class WorkflowSummary:
    """High-level summary of the compiled workflow."""
    phase_count: int = 0
    action_count: int = 0
    qa_gate_count: int = 0
    blocker_count: int = 0
    open_blocker_count: int = 0
    complete_action_count: int = 0
    next_recommended_actions: list[str] = field(default_factory=list)
    workflow_readiness: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_count": self.phase_count,
            "action_count": self.action_count,
            "qa_gate_count": self.qa_gate_count,
            "blocker_count": self.blocker_count,
            "open_blocker_count": self.open_blocker_count,
            "complete_action_count": self.complete_action_count,
            "next_recommended_actions": self.next_recommended_actions,
            "workflow_readiness": self.workflow_readiness,
        }


@dataclass
class ReplaySummary:
    """Summary of the event history and state reconstruction path."""
    event_count: int = 0
    replay_steps: list[dict[str, Any]] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "replay_steps": self.replay_steps,
            "actors": self.actors,
        }


@dataclass
class ExportLinks:
    """Available derived output locations."""
    links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"links": self.links}


@dataclass
class AdvisoryNotice:
    """Machine-readable advisory posture for all downstream consumers."""
    is_advisory: bool = True
    requires_oem_verification: bool = True
    requires_qualified_technician_review: bool = True
    does_not_replace_oem_procedure: bool = True
    does_not_certify_repair_completion: bool = True
    customer_owned_source_content: bool = True
    notice: str = (
        "RepairGraph outputs are advisory workflow intelligence derived from "
        "customer-supplied OEM repair information. They do not certify repair "
        "completion, OEM compliance, or repair quality. All outputs require "
        "verification by a qualified technician against applicable OEM procedures."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_advisory": self.is_advisory,
            "requires_oem_verification": self.requires_oem_verification,
            "requires_qualified_technician_review": self.requires_qualified_technician_review,
            "does_not_replace_oem_procedure": self.does_not_replace_oem_procedure,
            "does_not_certify_repair_completion": self.does_not_certify_repair_completion,
            "customer_owned_source_content": self.customer_owned_source_content,
            "notice": self.notice,
        }


@dataclass
class OperationalModel:
    """Canonical artifact produced by the RepairGraph Compiler.

    Every downstream product surface (insights, viewer, replay, reports, APIs)
    should derive its output from this model rather than re-parsing source
    documents or independently interpreting raw procedure data.

    The OperationalModel is domain-agnostic. Collision repair, aviation
    maintenance, industrial service, and other domains populate the
    domain_context section through domain adapters.
    """
    metadata: ModelMetadata
    source_manifest: SourceManifest
    domain_context: DomainContext
    evidence: EvidenceSummary
    topology: TopologyGraph | None
    state: RepairState | None
    workflow: WorkflowSummary
    replay: ReplaySummary
    insights: InsightPayload | None
    exports: ExportLinks
    advisory: AdvisoryNotice = field(default_factory=AdvisoryNotice)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full OperationalModel to a JSON-safe dict."""
        return {
            "schema_name": "repairgraph.core.operational_model",
            "metadata": self.metadata.to_dict(),
            "source_manifest": self.source_manifest.to_dict(),
            "domain_context": self.domain_context.to_dict(),
            "evidence": self.evidence.to_dict(),
            "topology": _topology_to_dict(self.topology),
            "state": _state_to_dict(self.state),
            "workflow": self.workflow.to_dict(),
            "replay": self.replay.to_dict(),
            "insights": self.insights.to_dict() if self.insights else None,
            "exports": self.exports.to_dict(),
            "advisory": self.advisory.to_dict(),
        }


# ---------------------------------------------------------------------------
# Internal serialization helpers for existing domain schemas
# ---------------------------------------------------------------------------

def _topology_to_dict(topology: TopologyGraph | None) -> dict[str, Any] | None:
    if topology is None:
        return None
    return {
        "zone_count": len(topology.zones),
        "relationship_count": len(topology.zone_relationships),
        "operation_region_count": len(topology.operation_regions),
        "structural_group_count": len(topology.structural_groups),
        "operation_stage_count": len(topology.operation_stages),
        "meta": topology.meta,
        "interpretation_note": topology.interpretation_note,
    }


def _state_to_dict(state: RepairState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "session_status": state.session.status,
        "current_phase": state.session.current_phase,
        "phase_count": len(state.phases),
        "action_count": len(state.actions),
        "qa_gate_count": len(state.qa_gates),
        "blocker_count": len(state.blockers),
        "event_count": len(state.events),
        "zone_count": len(state.zones),
        "open_blocker_count": sum(1 for b in state.blockers if b.status == "open"),
        "complete_action_count": sum(1 for a in state.actions if a.status == "complete"),
        "next_recommended_actions": list(state.next_recommended_actions),
    }
