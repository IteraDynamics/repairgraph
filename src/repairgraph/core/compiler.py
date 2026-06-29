"""
RepairGraph Compiler.

Orchestrates the full pipeline from domain adapter inputs through to a
canonical OperationalModel. The compiler assembles existing modules without
duplicating their logic.

Pipeline:
  domain_context ← DomainAdapter
  source_manifest ← intake classification
  topology        ← topology builder
  state           ← state initializer + event replay
  insights        ← insight engine
  OperationalModel ← all of the above assembled here

The compiler is domain-agnostic. Domain adapters supply the inputs that
make each compilation domain-specific.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

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
from repairgraph.insights.engine import build_insight_payload
from repairgraph.insights.replay_enrichment import enrich_replay_step
from repairgraph.intake.classify import classify_intake_packet, summarize_intake_manifest
from repairgraph.state.blockers import summarize_blockers
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.replay import build_state_diff, replay_repair_state, summarize_state_diff
from repairgraph.state.schema import RepairState
from repairgraph.topology.schema import TopologyGraph


class RepairGraphCompiler:
    """Orchestrates the RepairGraph compilation pipeline.

    Usage — compile from an existing RepairState (e.g. demo fixtures):

        compiler = RepairGraphCompiler()
        model = compiler.compile_from_state(
            state=projected_state,
            topology=topology_graph,
            adapter=collision_adapter,
            source_paths=[...],
        )

    Usage — compile from demo fixtures (golden path):

        compiler = RepairGraphCompiler()
        model = compiler.compile_demo(adapter=collision_adapter)
    """

    COMPILER_VERSION = "1.0.0"

    # ------------------------------------------------------------------
    # Primary compilation entry points
    # ------------------------------------------------------------------

    def compile_from_state(
        self,
        *,
        state: RepairState,
        topology: TopologyGraph | None = None,
        adapter: DomainAdapter | None = None,
        source_paths: list[Path] | None = None,
        initial_state: RepairState | None = None,
        events: list[Any] | None = None,
        export_links: dict[str, str] | None = None,
    ) -> OperationalModel:
        """Build an OperationalModel from an already-compiled RepairState.

        This is the primary entry point for existing code that already builds
        RepairState through existing module pipelines.
        """
        metadata = ModelMetadata.create(compiler_version=self.COMPILER_VERSION)

        source_manifest = self._build_source_manifest(source_paths, adapter)
        domain_context = adapter.build_domain_context() if adapter else _default_domain_context()
        evidence = self._build_evidence(state)
        workflow = self._build_workflow_summary(state)
        replay = self._build_replay_summary(state, initial_state, events)
        insights = build_insight_payload(state)
        exports = ExportLinks(links=export_links or {})

        return OperationalModel(
            metadata=metadata,
            source_manifest=source_manifest,
            domain_context=domain_context,
            evidence=evidence,
            topology=topology,
            state=state,
            workflow=workflow,
            replay=replay,
            insights=insights,
            exports=exports,
            advisory=AdvisoryNotice(),
        )

    def compile_demo(
        self,
        *,
        adapter: DomainAdapter | None = None,
    ) -> OperationalModel:
        """Compile an OperationalModel from the Honda Accord demo fixtures.

        This is the golden-path compilation path. All existing demo endpoints
        and the viewer continue to work by consuming this model.
        """
        from repairgraph.state.demo import (
            build_accord_demo_events,
            build_accord_initial_state,
            build_accord_projected_state,
        )
        from repairgraph.topology.builder import build_topology_graph
        from repairgraph.query.loader import load_procedure

        procedure = load_procedure("Honda", 2025, "Accord")
        topology = build_topology_graph(procedure)
        initial = build_accord_initial_state()
        events = build_accord_demo_events(initial)
        projected = build_accord_projected_state()

        export_links = {
            "workflow_report": "/internal/state/accord/report?view=workflow",
            "replay_report": "/internal/state/accord/report?view=replay",
            "intake_page": "/internal/intake",
            "visualization_json": "/internal/state/accord/visualization",
            "topology_viewer": "/internal/state/accord/topology-viewer",
            "executive_summary": "/internal/state/accord/report?view=executive",
        }

        return self.compile_from_state(
            state=projected,
            topology=topology,
            adapter=adapter,
            initial_state=initial,
            events=events,
            export_links=export_links,
        )

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_source_manifest(
        self,
        source_paths: list[Path] | None,
        adapter: DomainAdapter | None,
    ) -> SourceManifest:
        overrides: dict[str, Any] = {}
        if adapter is not None:
            overrides = adapter.build_source_manifest_overrides()

        if source_paths:
            manifest = classify_intake_packet(source_paths)
            return SourceManifest(
                source_count=len(manifest.files),
                filenames=[f.filename for f in manifest.files],
                detected_roles=manifest.detected_packet.detected_roles,
                missing_roles=manifest.missing_roles,
                readiness=manifest.readiness,
                extraction_warnings=[
                    d.message for d in manifest.diagnostics if d.severity == "warning"
                ],
            )

        return SourceManifest(
            source_count=overrides.get("source_count", 0),
            filenames=overrides.get("filenames", []),
            detected_roles=overrides.get("detected_roles", []),
            missing_roles=overrides.get("missing_roles", []),
            readiness=overrides.get("readiness", "incomplete"),
        )

    def _build_evidence(self, state: RepairState) -> EvidenceSummary:
        items: list[dict[str, Any]] = []
        confidence: dict[str, float] = {}

        for action in state.actions:
            if action.evidence:
                items.append({
                    "action_id": action.action_id,
                    "evidence": action.evidence,
                })

        for qa in state.qa_gates:
            if qa.evidence:
                items.append({
                    "gate_id": qa.gate_id,
                    "evidence": qa.evidence,
                })

        # Zone-level material classification as evidence
        material_zones = [z for z in state.zones if z.material_classification]
        if material_zones:
            confidence["material_classification"] = 0.85
            for zone in material_zones:
                items.append({
                    "zone_id": zone.zone_id,
                    "material_classification": zone.material_classification,
                    "risk_flags": zone.risk_flags,
                })

        return EvidenceSummary(
            evidence_items=items,
            confidence_by_category=confidence,
            requires_oem_verification=True,
        )

    def _build_workflow_summary(self, state: RepairState) -> WorkflowSummary:
        open_blockers = sum(1 for b in state.blockers if b.status == "open")
        complete_actions = sum(1 for a in state.actions if a.status == "complete")

        if open_blockers > 0:
            readiness = "blocked"
        elif complete_actions == len(state.actions) and state.actions:
            readiness = "complete"
        elif complete_actions > 0:
            readiness = "in_progress"
        else:
            readiness = "not_started"

        return WorkflowSummary(
            phase_count=len(state.phases),
            action_count=len(state.actions),
            qa_gate_count=len(state.qa_gates),
            blocker_count=len(state.blockers),
            open_blocker_count=open_blockers,
            complete_action_count=complete_actions,
            next_recommended_actions=list(state.next_recommended_actions),
            workflow_readiness=readiness,
        )

    def _build_replay_summary(
        self,
        state: RepairState,
        initial_state: RepairState | None,
        events: list[Any] | None,
    ) -> ReplaySummary:
        if not events or initial_state is None:
            return ReplaySummary(
                event_count=len(state.events),
                replay_steps=[],
                actors=list({e.actor for e in state.events}),
            )

        snapshots = replay_repair_state(initial_state, events)
        steps: list[dict[str, Any]] = []
        prev = initial_state
        for i, (event, snap) in enumerate(zip(events, snapshots)):
            diff = build_state_diff(prev, snap)
            diff_summary = summarize_state_diff(diff)
            raw_step = {
                "step": i + 1,
                "event": {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "target_type": event.target_type,
                    "target_id": event.target_id,
                    "notes": event.notes,
                },
                "state_summary": {
                    "session_status": snap.session.status,
                    "completed_action_count": sum(1 for a in snap.actions if a.status == "complete"),
                    "open_blocker_count": sum(1 for b in snap.blockers if b.status == "open"),
                    "active_phases": [p.name for p in snap.phases if p.status == "in_progress"],
                },
                "diff_summary": diff_summary,
            }
            steps.append(enrich_replay_step(raw_step))
            prev = snap

        actors = list({e.actor for e in events})
        return ReplaySummary(
            event_count=len(events),
            replay_steps=steps,
            actors=actors,
        )


def _default_domain_context() -> DomainContext:
    return DomainContext(
        domain="generic",
        display_label="Procedural Repair",
        context_data={},
    )
