"""
Architecture stress test: does the "domain-agnostic core" claim in
operational_model.py actually hold?

Not a second product. Compiles a genuinely different domain (aviation
maintenance task card) through the *unmodified* RepairGraphCompiler,
state-projection engine, and insights engine already used by collision
repair, using only the generic public surface:

    RepairState / RepairEvent / project_repair_state  (state/)
    RepairGraphCompiler.compile_from_state             (core/compiler.py)
    DomainAdapter protocol                             (core/interfaces.py)

The aviation fixture (tests/fixtures/aviation_task_card.py) deliberately
does NOT use initialize_repair_state, build_operation_sequence,
generate_qa_checklist, or build_topology_graph — those are collision-coupled
helpers, not core. Using them would prove nothing about portability.

See docs/ARCHITECTURE_DERISK.md for the full findings writeup, including
what this test proved holds and what it found still coupled to collision
repair (insights engine rule selection, topology zone classification).
"""
from __future__ import annotations

import json

import pytest

from repairgraph.adapters.aviation import AviationDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.core.operational_model import OperationalModel
from repairgraph.state.events import (
    action_completed_event,
    action_started_event,
    blocker_resolved_event,
    qa_gate_passed_event,
)
from repairgraph.state.project import project_repair_state
from repairgraph.state.replay import build_state_diff

from tests.fixtures.aviation_task_card import build_aviation_initial_state


@pytest.fixture
def aviation_state():
    return build_aviation_initial_state()


@pytest.fixture
def aviation_adapter():
    return AviationDomainAdapter(
        aircraft_type="A320-200",
        registration="N12345",
        ata_chapter="32",
        ata_chapter_label="Landing Gear",
        task_card_id="TC-32-11-04",
        check_type="100-hour",
        airworthiness_directives=["AD-2024-11-07"],
    )


@pytest.fixture
def aviation_model(aviation_state, aviation_adapter):
    return RepairGraphCompiler().compile_from_state(
        state=aviation_state, topology=None, adapter=aviation_adapter,
    )


# ---------------------------------------------------------------------------
# The adapter protocol genuinely generalizes
# ---------------------------------------------------------------------------

class TestAdapterProtocol:
    def test_satisfies_domain_adapter_protocol(self, aviation_adapter):
        from repairgraph.core.interfaces import DomainAdapter
        assert isinstance(aviation_adapter, DomainAdapter)

    def test_domain_identifier_is_aviation_not_collision(self, aviation_adapter):
        assert aviation_adapter.domain == "aviation_maintenance"

    def test_display_label_has_no_collision_vocabulary(self, aviation_adapter):
        label = aviation_adapter._build_display_label()
        for word in ("oem", "vehicle", "collision", "accord", "honda"):
            assert word not in label.lower()

    def test_from_repair_state_reconstructs_adapter(self, aviation_state):
        rebuilt = AviationDomainAdapter.from_repair_state(aviation_state)
        assert rebuilt.task_card_id == aviation_state.session.operation


# ---------------------------------------------------------------------------
# The unmodified compiler produces a valid OperationalModel
# ---------------------------------------------------------------------------

class TestCompilerPortability:
    def test_compiles_without_modification(self, aviation_model):
        assert isinstance(aviation_model, OperationalModel)

    def test_domain_context_reflects_aviation(self, aviation_model):
        assert aviation_model.domain_context.domain == "aviation_maintenance"
        assert "TC-32-11-04" in aviation_model.domain_context.display_label

    def test_workflow_summary_counts_correct(self, aviation_model, aviation_state):
        wf = aviation_model.workflow
        assert wf.phase_count == len(aviation_state.phases)
        assert wf.action_count == len(aviation_state.actions)
        assert wf.qa_gate_count == len(aviation_state.qa_gates)
        assert wf.blocker_count == len(aviation_state.blockers)

    def test_workflow_readiness_blocked_by_open_critical_blocker(self, aviation_model):
        assert aviation_model.workflow.workflow_readiness == "blocked"

    def test_topology_none_is_handled(self, aviation_model):
        # Aviation task cards don't inherently need spatial zone topology —
        # the compiler and OperationalModel must accept topology=None cleanly.
        assert aviation_model.topology is None

    def test_advisory_notice_is_domain_neutral(self, aviation_model):
        notice = aviation_model.advisory.to_dict()
        assert notice["is_advisory"] is True
        assert "OEM" in notice["notice"]  # inherited wording; see findings doc

    def test_model_is_fully_json_serializable(self, aviation_model):
        json.dumps(aviation_model.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# State progression (event engine) generalizes
# ---------------------------------------------------------------------------

class TestEventEnginePortability:
    def test_qa_gate_passed_resolves_and_unblocks(self, aviation_state):
        events = [
            qa_gate_passed_event(gate_id="qa:airworthiness:critical:1", actor="inspector"),
            blocker_resolved_event(blocker_id="blocker:qa:airworthiness:critical:1", actor="inspector"),
        ]
        projected = project_repair_state(aviation_state, events)

        gate = next(g for g in projected.qa_gates if g.gate_id == "qa:airworthiness:critical:1")
        assert gate.status == "passed"
        assert all(b.status == "resolved" for b in projected.blockers)

    def test_action_lifecycle_started_then_completed(self, aviation_state):
        events = [
            action_started_event(action_id="chock_aircraft:main_gear", actor="mechanic"),
            action_completed_event(action_id="chock_aircraft:main_gear", actor="mechanic"),
        ]
        projected = project_repair_state(aviation_state, events)

        action = next(a for a in projected.actions if a.action_id == "chock_aircraft:main_gear")
        assert action.status == "complete"
        phase = next(p for p in projected.phases if p.phase == 1)
        assert "chock_aircraft:main_gear" in phase.completed_actions

    def test_recompiled_model_reflects_progression(self, aviation_state, aviation_adapter):
        events = [
            qa_gate_passed_event(gate_id="qa:airworthiness:critical:1", actor="inspector"),
            blocker_resolved_event(blocker_id="blocker:qa:airworthiness:critical:1", actor="inspector"),
        ]
        projected = project_repair_state(aviation_state, events)
        model = RepairGraphCompiler().compile_from_state(
            state=projected, topology=None, adapter=aviation_adapter,
            initial_state=aviation_state, events=events,
        )
        assert model.workflow.workflow_readiness != "blocked"
        assert model.replay.event_count == 2

    def test_state_diff_detects_aviation_changes(self, aviation_state):
        events = [action_started_event(action_id="chock_aircraft:main_gear", actor="mechanic")]
        projected = project_repair_state(aviation_state, events)
        diff = build_state_diff(aviation_state, projected)
        assert "actions" in diff
        assert "chock_aircraft:main_gear" in diff["actions"]


# ---------------------------------------------------------------------------
# Documented coupling: insights engine is NOT yet domain-gated
# ---------------------------------------------------------------------------

class TestKnownCouplingInsightsEngine:
    """These tests document current behavior, not desired behavior — see
    docs/ARCHITECTURE_DERISK.md 'Findings' section. build_insight_payload
    runs collision-specific rule modules (material/compliance) unconditionally
    regardless of domain_context.domain. It does not crash on aviation data
    (rules check for absent fields and simply find nothing) except for one
    always-fires rule that produces a collision-flavored false positive.
    """

    def test_insights_engine_does_not_crash_on_aviation_state(self, aviation_state):
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state)
        assert payload is not None

    def test_insights_engine_produces_collision_flavored_false_positive(self, aviation_state):
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state)
        finding_ids = {f.finding_id for f in payload.findings}
        # 'calibration' has no meaning for a landing gear task card; this
        # fires because compliance_findings always checks for a calibration
        # QA gate category with no domain gate. Documented, not desired.
        assert "compliance_calibration_not_identified" in finding_ids
