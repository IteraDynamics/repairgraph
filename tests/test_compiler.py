"""Tests for the RepairGraph Compiler."""
from __future__ import annotations

import pytest

from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.core.operational_model import OperationalModel
from repairgraph.adapters.collision import CollisionDomainAdapter


class TestRepairGraphCompilerDemo:
    """Test that the compiler produces a valid OperationalModel from demo fixtures."""

    def setup_method(self):
        adapter = CollisionDomainAdapter(
            oem="Honda",
            year=2025,
            model="Accord",
            operation="quarter_panel_replacement",
        )
        self.compiler = RepairGraphCompiler()
        self.model = self.compiler.compile_demo(adapter=adapter)

    def test_returns_operational_model(self):
        assert isinstance(self.model, OperationalModel)

    def test_metadata_populated(self):
        assert self.model.metadata.model_id
        assert self.model.metadata.schema_version == "1.0.0"
        assert self.model.metadata.advisory is True

    def test_domain_context_is_collision(self):
        assert self.model.domain_context.domain == "collision_repair"
        data = self.model.domain_context.context_data
        assert data["vehicle"]["oem"] == "Honda"
        assert data["vehicle"]["year"] == 2025
        assert data["vehicle"]["model"] == "Accord"

    def test_state_populated(self):
        assert self.model.state is not None
        assert len(self.model.state.phases) > 0
        assert len(self.model.state.actions) > 0

    def test_topology_populated(self):
        assert self.model.topology is not None
        assert len(self.model.topology.zones) > 0

    def test_insights_populated(self):
        assert self.model.insights is not None
        assert self.model.insights.overall_status in (
            "blocked", "at_risk", "ready", "complete", "unknown"
        )

    def test_workflow_summary_consistent_with_state(self):
        w = self.model.workflow
        s = self.model.state
        assert w.phase_count == len(s.phases)
        assert w.action_count == len(s.actions)
        assert w.qa_gate_count == len(s.qa_gates)

    def test_replay_has_steps(self):
        assert self.model.replay.event_count > 0
        assert len(self.model.replay.replay_steps) > 0

    def test_exports_have_links(self):
        assert len(self.model.exports.links) > 0
        assert "topology_viewer" in self.model.exports.links

    def test_advisory_notice(self):
        assert self.model.advisory.is_advisory is True
        assert self.model.advisory.requires_oem_verification is True

    def test_to_dict_serializable(self):
        import json
        d = self.model.to_dict()
        # Should not raise
        serialized = json.dumps(d, default=str)
        assert len(serialized) > 100


class TestRepairGraphCompilerFromState:
    """Test compile_from_state with an existing RepairState."""

    def test_compile_from_state_no_adapter(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        compiler = RepairGraphCompiler()
        model = compiler.compile_from_state(state=state)
        assert isinstance(model, OperationalModel)
        assert model.domain_context.domain == "generic"

    def test_compile_from_state_with_adapter(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        adapter = CollisionDomainAdapter.from_repair_state(state)
        compiler = RepairGraphCompiler()
        model = compiler.compile_from_state(state=state, adapter=adapter)
        assert model.domain_context.domain == "collision_repair"

    def test_workflow_readiness_blocked_when_blockers_open(self):
        from repairgraph.state.demo import build_accord_projected_state
        state = build_accord_projected_state()
        open_blockers = sum(1 for b in state.blockers if b.status == "open")
        compiler = RepairGraphCompiler()
        model = compiler.compile_from_state(state=state)
        if open_blockers > 0:
            assert model.workflow.workflow_readiness == "blocked"
