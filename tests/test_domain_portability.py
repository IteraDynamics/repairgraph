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
# Fixed coupling: insights engine is now domain-gated
# ---------------------------------------------------------------------------
#
# Originally documented here as a coupling finding (docs/ARCHITECTURE_DERISK.md
# finding #1): build_insight_payload ran collision-specific rule modules
# (material/compliance) unconditionally regardless of domain, producing a
# false-positive 'no calibration identified' finding on aviation data where
# calibration has no meaning. Fixed via insights/engine.py's
# DOMAIN_RULE_MODULES gating. These tests now pin the fix down as a
# regression trap — if domain gating breaks, these fail.

class TestInsightsEngineIsDomainGated:
    def test_does_not_crash_on_aviation_state(self, aviation_state):
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state, domain="aviation_maintenance")
        assert payload is not None

    def test_collision_false_positive_is_gone_when_domain_is_correct(self, aviation_state):
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state, domain="aviation_maintenance")
        finding_ids = {f.finding_id for f in payload.findings}
        # 'calibration' has no meaning for a landing gear task card; this
        # must not fire when the aviation domain is correctly passed through.
        assert "compliance_calibration_not_identified" not in finding_ids
        assert not any(f.category in ("material", "compliance") for f in payload.findings)

    def test_generic_findings_still_fire_for_aviation(self, aviation_state):
        # QA/workflow/milestone findings are domain-neutral and must still
        # surface — gating removes collision-specific findings, not all of them.
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state, domain="aviation_maintenance")
        finding_ids = {f.finding_id for f in payload.findings}
        assert "qa_critical_open_qa:airworthiness:critical:1" in finding_ids

    def test_default_domain_preserves_collision_behavior(self, aviation_state):
        # Backward compatibility: existing collision callers that don't pass
        # domain= still get collision-specific rules by default.
        from repairgraph.insights.engine import build_insight_payload
        payload = build_insight_payload(aviation_state)  # no domain= passed
        finding_ids = {f.finding_id for f in payload.findings}
        assert "compliance_calibration_not_identified" in finding_ids

    def test_compiled_model_passes_domain_through_automatically(
        self, aviation_state, aviation_adapter
    ):
        # End-to-end: compile_from_state threads domain_context.domain into
        # build_insight_payload without the caller doing anything extra.
        model = RepairGraphCompiler().compile_from_state(
            state=aviation_state, topology=None, adapter=aviation_adapter,
        )
        finding_ids = {f.finding_id for f in model.insights.findings}
        assert "compliance_calibration_not_identified" not in finding_ids


# ---------------------------------------------------------------------------
# Fixed coupling: topology zone classification is now pluggable
# ---------------------------------------------------------------------------
#
# Originally documented as finding #2: topology/builder.py's zone classifier
# was hardcoded collision vocabulary (pillar/rail/sill/stiffener), and
# RepairZone validated zone_type/vehicle_section/structural_tier against
# closed collision-only enums, so even a custom classifier's output would be
# rejected. Fixed by making build_topology_graph accept a ZoneClassifier and
# relaxing RepairZone's validation to non-empty strings rather than a closed
# set (topology/schema.py).

class TestTopologyZoneClassificationIsPluggable:
    def test_custom_classifier_produces_non_collision_zone_types(self):
        from repairgraph.topology.builder import build_topology_graph

        def aviation_zone_classifier(zone_id: str) -> tuple[str, str, str]:
            name = zone_id.lower()
            zone_type = "landing_gear" if "gear" in name else "unknown"
            return zone_type, "main", "primary_structure"

        procedure = {
            "oem": "Airbus", "year": 0, "model": "A320-200", "operation": "gear_inspection",
            "spatial_relationships": [
                {"source": "main_gear_strut", "relationship": "adjacent_to", "target": "main_gear_axle"}
            ],
            "dependencies": [], "sectioning_locations": [],
        }
        topology = build_topology_graph(procedure, zone_classifier=aviation_zone_classifier)

        zone_types = {z.zone_type for z in topology.zones}
        assert zone_types == {"landing_gear"}

    def test_default_classifier_unchanged_for_collision_data(self):
        from repairgraph.topology.builder import (
            _classify_zone,
            collision_zone_classifier,
        )
        assert _classify_zone("rear_pillar_gutter") == collision_zone_classifier(
            "rear_pillar_gutter"
        )
        assert collision_zone_classifier("rear_pillar_gutter") == (
            "gutter", "rear", "inner_structure",
        )
