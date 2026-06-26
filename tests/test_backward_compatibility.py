"""
Backward compatibility tests.

Verifies that all existing APIs, demo flows, and data pipelines continue
to work unchanged after the introduction of the OperationalModel layer.

The OperationalModel is additive. Nothing existing should break.
"""
from __future__ import annotations

import pytest


class TestDemoOrchestratorUnchanged:
    """The existing demo orchestrator must continue producing valid payloads."""

    def test_build_intake_demo_payload(self):
        from repairgraph.demo.orchestrator import build_intake_demo_payload
        payload = build_intake_demo_payload()
        assert payload["schema_name"] == "repairgraph.demo.intake"
        assert "files" in payload
        assert "detected_packet" in payload

    def test_build_workflow_demo_payload(self):
        from repairgraph.demo.orchestrator import build_workflow_demo_payload
        payload = build_workflow_demo_payload()
        assert payload["schema_name"] == "repairgraph.demo.workflow"
        assert "replay_steps" in payload
        assert "phases" in payload

    def test_build_insight_demo_payload(self):
        from repairgraph.demo.orchestrator import build_insight_demo_payload
        payload = build_insight_demo_payload()
        assert "findings" in payload
        assert "overall_status" in payload

    def test_build_full_demo_payload(self):
        from repairgraph.demo.orchestrator import build_full_demo_payload
        payload = build_full_demo_payload()
        assert "intake" in payload
        assert "workflow" in payload
        assert "insights" in payload
        assert "export_links" in payload


class TestRepairStateUnchanged:
    """The RepairState model must continue functioning as before."""

    def test_build_accord_initial_state(self):
        from repairgraph.state.demo import build_accord_initial_state
        state = build_accord_initial_state()
        assert state.session.oem == "Honda"
        assert len(state.phases) > 0
        assert len(state.actions) > 0

    def test_build_accord_projected_state(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        assert state.session.status in ("in_progress", "blocked", "ready_for_review", "complete")

    def test_replay_still_works(self):
        from repairgraph.state.demo import build_accord_demo_events, build_accord_initial_state
        from repairgraph.state.replay import replay_repair_state
        initial = build_accord_initial_state()
        events = build_accord_demo_events(initial)
        snapshots = replay_repair_state(initial, events)
        assert len(snapshots) == len(events)


class TestTopologyUnchanged:
    """The topology builder must continue functioning as before."""

    def test_build_topology_graph(self):
        from repairgraph.topology.builder import build_topology_graph
        from repairgraph.query.loader import load_procedure
        procedure = load_procedure("Honda", 2025, "Accord")
        topo = build_topology_graph(procedure)
        assert len(topo.zones) > 0
        assert len(topo.zone_relationships) > 0


class TestInsightEngineUnchanged:
    """The insight engine must continue functioning as before."""

    def test_build_insight_payload(self):
        from repairgraph.insights.engine import build_insight_payload
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        payload = build_insight_payload(state)
        assert payload.schema_name == "repairgraph.insights.payload"
        assert isinstance(payload.findings, list)


class TestIntakeUnchanged:
    """The intake classifier must continue functioning as before."""

    def test_classify_intake_packet(self):
        from pathlib import Path
        from repairgraph.intake.classify import classify_intake_packet
        fixture = Path(__file__).parent / "fixtures" / "intake" / "toyota_packet"
        if not fixture.exists():
            pytest.skip("Toyota fixture not available")
        paths = sorted(fixture.glob("*.txt"))
        manifest = classify_intake_packet(paths)
        assert manifest.intake_id
        assert len(manifest.files) > 0


class TestOperationalModelLayerAdditive:
    """Verify the new OperationalModel layer is additive — imports don't break anything."""

    def test_core_package_importable(self):
        import repairgraph.core
        assert hasattr(repairgraph.core, "OperationalModel")
        assert hasattr(repairgraph.core, "RepairGraphCompiler")
        assert hasattr(repairgraph.core, "DomainAdapter")

    def test_adapters_package_importable(self):
        import repairgraph.adapters
        assert hasattr(repairgraph.adapters, "CollisionDomainAdapter")

    def test_operational_model_does_not_shadow_existing_schemas(self):
        from repairgraph.state.schema import RepairState
        from repairgraph.topology.schema import TopologyGraph
        from repairgraph.insights.schema import InsightPayload
        # These must still be importable from their original locations
        assert RepairState is not None
        assert TopologyGraph is not None
        assert InsightPayload is not None
