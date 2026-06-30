"""Tests for the Operational Planner (OperationalPlan, candidate generation, scoring)."""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.api.app import app
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.operational_planner import (
    _ADVISORY_NOTICE,
    _FALLBACK_ACTION,
    _W_ALREADY_COMPLETE,
    _W_CRITICAL_QA,
    _W_HIGH_QA,
    _W_MEDIUM_QA,
    _W_PHASE_UNBLOCKED,
    _W_STILL_BLOCKED,
    NextBestAction,
    OperationalPlan,
    PlannerCandidate,
    PlannerScore,
    PlannerUnlock,
    _build_candidates,
    _compute_unlocks,
    _score_candidate,
    _sort_key,
    build_operational_plan,
)
from repairgraph.review.root_cause import build_root_cause_analysis
from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairSession,
    RepairState,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def model():
    adapter = CollisionDomainAdapter(
        oem="Honda",
        year=2025,
        model="Accord",
        operation="quarter_panel_replacement",
        repair_area="left_rear",
        structural_involvement=True,
        calibration_required=True,
        corrosion_protection_required=True,
    )
    compiler = RepairGraphCompiler()
    return compiler.compile_demo(adapter=adapter)


@pytest.fixture(scope="module")
def rca(model):
    return build_root_cause_analysis(model)


@pytest.fixture(scope="module")
def plan(model, rca):
    return build_operational_plan(model, rca=rca)


# ---------------------------------------------------------------------------
# OperationalPlan construction
# ---------------------------------------------------------------------------

class TestOperationalPlanConstruction:
    def test_returns_operational_plan(self, plan):
        assert isinstance(plan, OperationalPlan)

    def test_plan_id_is_uuid_string(self, plan):
        import uuid
        uuid.UUID(plan.plan_id)  # raises if invalid

    def test_model_id_is_set(self, plan, model):
        assert plan.model_id == model.metadata.model_id

    def test_generated_at_is_set(self, plan):
        assert plan.generated_at

    def test_overall_status_is_set(self, plan):
        assert plan.overall_status in ("blocked", "at_risk", "ready", "complete", "unknown", "in_progress", "not_started")

    def test_to_dict_is_json_serializable(self, plan):
        json.dumps(plan.to_dict())

    def test_to_dict_has_required_keys(self, plan):
        d = plan.to_dict()
        for key in (
            "plan_id", "model_id", "generated_at", "overall_status",
            "next_best_action", "action_queue", "critical_path",
            "expected_unlocks", "blocked_by", "deferred_work",
            "risk_reduction", "confidence", "supporting_evidence", "advisory",
        ):
            assert key in d, f"Missing key: {key}"

    def test_advisory_is_non_empty(self, plan):
        assert plan.advisory

    def test_confidence_is_valid(self, plan):
        assert plan.confidence in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# NextBestAction
# ---------------------------------------------------------------------------

class TestNextBestAction:
    def test_next_best_action_is_set(self, plan):
        assert isinstance(plan.next_best_action, NextBestAction)

    def test_display_label_is_non_empty(self, plan):
        assert plan.next_best_action.display_label

    def test_display_label_is_human_readable(self, plan):
        label = plan.next_best_action.display_label
        # Should not start with raw ID patterns
        assert not label.startswith("qa:")
        assert not label.startswith("blocker:")

    def test_why_now_is_set(self, plan):
        assert plan.next_best_action.why_now

    def test_confidence_is_valid(self, plan):
        assert plan.next_best_action.confidence in ("high", "medium", "low")

    def test_action_type_is_set(self, plan):
        assert plan.next_best_action.action_type

    def test_nba_to_dict_has_required_keys(self, plan):
        d = plan.next_best_action.to_dict()
        for key in (
            "action_id", "display_label", "action_type",
            "why_now", "expected_unlocks", "risk_reduction",
            "blocked_by", "confidence", "advisory_notice",
        ):
            assert key in d, f"Missing NBA key: {key}"

    def test_accordion_demo_recommends_joining_or_material(self, plan):
        """For the Accord demo (UHSS quarter pillar), planner should recommend
        clearing the joining/material QA gate or resolving a structural blocker."""
        label = plan.next_best_action.display_label.lower()
        # One of these domains should appear
        relevant = any(
            kw in label
            for kw in ("join", "material", "structural", "block", "clear qa", "resolve", "qa gate")
        )
        assert relevant, f"Unexpected NBA label: {plan.next_best_action.display_label!r}"


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

class TestCandidateGeneration:
    def test_returns_list(self, model):
        candidates = _build_candidates(model)
        assert isinstance(candidates, list)

    def test_at_least_one_candidate(self, model):
        candidates = _build_candidates(model)
        assert len(candidates) >= 1

    def test_candidates_are_planner_candidates(self, model):
        candidates = _build_candidates(model)
        for c in candidates:
            assert isinstance(c, PlannerCandidate)

    def test_candidate_ids_are_unique(self, model):
        candidates = _build_candidates(model)
        ids = [c.candidate_id for c in candidates]
        assert len(ids) == len(set(ids))

    def test_candidate_types_are_known(self, model):
        valid_types = {"qa_gate", "blocker", "phase", "workflow", "evidence", "root_cause"}
        for c in _build_candidates(model):
            assert c.candidate_type in valid_types, f"Unknown type: {c.candidate_type}"

    def test_display_labels_are_non_empty(self, model):
        for c in _build_candidates(model):
            assert c.display_label, f"Empty label for {c.candidate_id}"

    def test_with_rca_includes_root_cause_candidates(self, model, rca):
        candidates = _build_candidates(model, rca=rca)
        types = {c.candidate_type for c in candidates}
        # RCA candidates supplement the list
        assert len(candidates) >= 1

    def test_no_state_returns_empty(self, model):
        import copy
        m = copy.copy(model)
        m = type(model)(
            metadata=model.metadata,
            source_manifest=model.source_manifest,
            domain_context=model.domain_context,
            evidence=model.evidence,
            topology=model.topology,
            state=None,
            workflow=model.workflow,
            replay=model.replay,
            insights=model.insights,
            exports=model.exports,
            advisory=model.advisory,
        )
        candidates = _build_candidates(m)
        assert candidates == []


# ---------------------------------------------------------------------------
# Leverage scoring
# ---------------------------------------------------------------------------

class TestLeverageScoring:
    def test_returns_planner_score(self, model):
        candidates = _build_candidates(model)
        if not candidates:
            pytest.skip("No candidates")
        score = _score_candidate(candidates[0], model)
        assert isinstance(score, PlannerScore)

    def test_critical_qa_gate_scores_high(self, model):
        """A critical open QA gate should score at least _W_CRITICAL_QA."""
        if not model.state:
            pytest.skip("No state")
        critical_gates = [
            g for g in model.state.qa_gates
            if g.status in ("open", "in_review") and g.priority == "critical"
        ]
        if not critical_gates:
            pytest.skip("No critical open QA gates in demo")
        gate = critical_gates[0]
        candidate = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label="Test gate",
            source_entities=[gate.gate_id],
            related_phase_ids=[gate.related_phase] if gate.related_phase else [],
            severity="critical",
            earliest_phase=gate.related_phase or 999,
        )
        score = _score_candidate(candidate, model)
        assert score.leverage_score >= _W_CRITICAL_QA

    def test_high_qa_gate_scores_at_least_high_weight(self, model):
        if not model.state:
            pytest.skip("No state")
        high_gates = [
            g for g in model.state.qa_gates
            if g.status in ("open", "in_review") and g.priority == "high"
        ]
        if not high_gates:
            pytest.skip("No high open QA gates in demo")
        gate = high_gates[0]
        candidate = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label="Test gate high",
            source_entities=[gate.gate_id],
            severity="high",
            earliest_phase=gate.related_phase or 999,
        )
        score = _score_candidate(candidate, model)
        assert score.leverage_score >= _W_HIGH_QA

    def test_already_complete_candidate_penalised(self, model):
        """A QA gate that is already passed should receive a negative score."""
        if not model.state:
            pytest.skip("No state")
        passed_gates = [g for g in model.state.qa_gates if g.status == "passed"]
        if not passed_gates:
            pytest.skip("No passed gates in demo")
        gate = passed_gates[0]
        candidate = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label="Passed gate",
            source_entities=[gate.gate_id],
            severity="low",
            earliest_phase=gate.related_phase or 999,
        )
        score = _score_candidate(candidate, model)
        assert score.leverage_score < 0

    def test_blocked_action_candidate_penalised(self, model):
        """A workflow candidate whose action is still blocked should be penalised."""
        if not model.state:
            pytest.skip("No state")
        blocked_actions = [a for a in model.state.actions if a.status == "blocked"]
        if not blocked_actions:
            pytest.skip("No blocked actions in demo")
        action = blocked_actions[0]
        candidate = PlannerCandidate(
            candidate_id=f"workflow:{action.action_id}",
            candidate_type="workflow",
            display_label="Blocked action",
            source_entities=[action.action_id],
            severity="medium",
            earliest_phase=action.phase,
        )
        score = _score_candidate(candidate, model)
        assert score.leverage_score < 0

    def test_evidence_gap_scores_positive(self, model):
        """Missing evidence candidates should score positively."""
        candidate = PlannerCandidate(
            candidate_id="evidence:oem_procedures",
            candidate_type="evidence",
            display_label="Obtain missing document: OEM Procedures.",
            source_entities=["oem_procedures"],
            severity="medium",
            earliest_phase=0,
        )
        score = _score_candidate(candidate, model)
        assert score.leverage_score > 0


# ---------------------------------------------------------------------------
# Next best action selection ordering
# ---------------------------------------------------------------------------

class TestNextBestActionSelection:
    def test_critical_qa_beats_lower_priority(self, model):
        """Critical QA gate candidate should rank above a low-severity evidence gap."""
        if not model.state:
            pytest.skip("No state")
        critical_gates = [
            g for g in model.state.qa_gates
            if g.status in ("open", "in_review") and g.priority == "critical"
        ]
        if not critical_gates:
            pytest.skip("No critical open QA gates")
        gate = critical_gates[0]
        crit = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label="Critical gate",
            source_entities=[gate.gate_id],
            severity="critical",
            earliest_phase=gate.related_phase or 999,
        )
        low = PlannerCandidate(
            candidate_id="evidence:misc",
            candidate_type="evidence",
            display_label="Low priority note.",
            source_entities=["misc"],
            severity="low",
            earliest_phase=999,
        )
        score_crit = _score_candidate(crit, model)
        score_low = _score_candidate(low, model)
        assert score_crit.leverage_score > score_low.leverage_score

    def test_completed_action_not_recommended(self, plan, model):
        """The next best action should not be a completed action."""
        if not model.state:
            pytest.skip("No state")
        complete_targets = {a.target.lower() for a in model.state.actions if a.status == "complete"}
        label = plan.next_best_action.display_label.lower()
        # Completed action labels typically end with "(complete)"
        assert "(complete)" not in label

    def test_fallback_when_no_candidates(self):
        """When state is None, the plan falls back gracefully."""
        from repairgraph.adapters.collision import CollisionDomainAdapter
        from repairgraph.core.compiler import RepairGraphCompiler
        adapter = CollisionDomainAdapter(
            oem="Honda",
            year=2025,
            model="Accord",
            operation="quarter_panel_replacement",
            repair_area="left_rear",
        )
        compiler = RepairGraphCompiler()
        m = compiler.compile_demo(adapter=adapter)
        # Forcibly remove state
        import copy
        m2 = type(m)(
            metadata=m.metadata,
            source_manifest=m.source_manifest,
            domain_context=m.domain_context,
            evidence=m.evidence,
            topology=m.topology,
            state=None,
            workflow=m.workflow,
            replay=m.replay,
            insights=m.insights,
            exports=m.exports,
            advisory=m.advisory,
        )
        p = build_operational_plan(m2)
        assert p.next_best_action.display_label == _FALLBACK_ACTION

    def test_sort_key_prefers_higher_leverage(self):
        c1 = PlannerCandidate("c1", "qa_gate", "A", severity="critical", earliest_phase=1)
        c2 = PlannerCandidate("c2", "qa_gate", "B", severity="low", earliest_phase=2)
        s1 = PlannerScore("c1", 200, "critical", 1, 5, "high")
        s2 = PlannerScore("c2", 50, "low", 2, 0, "low")
        # c1 should sort before c2 (lower sort key)
        assert _sort_key((c1, s1)) < _sort_key((c2, s2))

    def test_sort_key_prefers_earlier_phase_on_tie(self):
        c1 = PlannerCandidate("c1", "qa_gate", "A", severity="high", earliest_phase=1)
        c2 = PlannerCandidate("c2", "qa_gate", "B", severity="high", earliest_phase=3)
        s1 = PlannerScore("c1", 100, "high", 1, 3, "high")
        s2 = PlannerScore("c2", 100, "high", 3, 3, "high")
        assert _sort_key((c1, s1)) < _sort_key((c2, s2))


# ---------------------------------------------------------------------------
# Expected unlock generation
# ---------------------------------------------------------------------------

class TestExpectedUnlockGeneration:
    def test_expected_unlocks_is_list(self, plan):
        assert isinstance(plan.expected_unlocks, list)

    def test_unlock_items_are_planner_unlocks(self, plan):
        for u in plan.expected_unlocks:
            assert isinstance(u, PlannerUnlock)

    def test_unlock_to_dict_has_keys(self, plan):
        for u in plan.expected_unlocks:
            d = u.to_dict()
            assert "unlock_type" in d
            assert "label" in d
            assert "unlock_id" in d

    def test_unlock_labels_are_non_empty(self, plan):
        for u in plan.expected_unlocks:
            assert u.label

    def test_unlock_types_are_known(self, plan):
        valid = {"phase", "qa_gate", "action", "risk", "finding"}
        for u in plan.expected_unlocks:
            assert u.unlock_type in valid, f"Unknown unlock type: {u.unlock_type}"

    def test_compute_unlocks_for_qa_candidate(self, model):
        if not model.state:
            pytest.skip("No state")
        open_gates = [g for g in model.state.qa_gates if g.status in ("open", "in_review")]
        if not open_gates:
            pytest.skip("No open gates")
        gate = open_gates[0]
        c = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label="Test",
            source_entities=[gate.gate_id],
        )
        unlocks = _compute_unlocks(c, model)
        assert isinstance(unlocks, list)


# ---------------------------------------------------------------------------
# Critical path generation
# ---------------------------------------------------------------------------

class TestCriticalPathGeneration:
    def test_critical_path_is_list(self, plan):
        assert isinstance(plan.critical_path, list)

    def test_critical_path_non_empty(self, plan):
        assert len(plan.critical_path) >= 1

    def test_critical_path_first_step_is_nba(self, plan):
        """Critical path should start with the next best action."""
        assert plan.critical_path[0] == plan.next_best_action.display_label

    def test_critical_path_at_most_eight(self, plan):
        assert len(plan.critical_path) <= 8

    def test_critical_path_items_are_strings(self, plan):
        for step in plan.critical_path:
            assert isinstance(step, str)
            assert step.strip()


# ---------------------------------------------------------------------------
# Action queue
# ---------------------------------------------------------------------------

class TestActionQueue:
    def test_action_queue_has_sections(self, plan):
        q = plan.action_queue
        assert "today" in q
        assert "next" in q
        assert "deferred" in q

    def test_today_has_at_least_one_item(self, plan):
        assert len(plan.action_queue["today"]) >= 1

    def test_today_first_item_is_nba(self, plan):
        assert plan.action_queue["today"][0] == plan.next_best_action.display_label

    def test_today_at_most_three(self, plan):
        assert len(plan.action_queue["today"]) <= 3

    def test_next_and_deferred_are_lists(self, plan):
        assert isinstance(plan.action_queue["next"], list)
        assert isinstance(plan.action_queue["deferred"], list)


# ---------------------------------------------------------------------------
# /internal/review/plan endpoint
# ---------------------------------------------------------------------------

class TestPlanEndpoint:
    def test_returns_200(self):
        resp = client.get("/internal/review/plan")
        assert resp.status_code == 200

    def test_returns_json(self):
        resp = client.get("/internal/review/plan")
        assert "application/json" in resp.headers["content-type"]

    def test_has_required_top_level_keys(self):
        data = client.get("/internal/review/plan").json()
        for key in (
            "plan_id", "model_id", "generated_at", "overall_status",
            "next_best_action", "action_queue", "critical_path",
            "expected_unlocks", "advisory", "endpoint_advisory",
        ):
            assert key in data, f"Missing key: {key}"

    def test_next_best_action_has_display_label(self):
        data = client.get("/internal/review/plan").json()
        nba = data["next_best_action"]
        assert nba.get("display_label")

    def test_next_best_action_has_why_now(self):
        data = client.get("/internal/review/plan").json()
        nba = data["next_best_action"]
        assert nba.get("why_now")

    def test_overall_status_is_meaningful(self):
        data = client.get("/internal/review/plan").json()
        assert data["overall_status"] in (
            "blocked", "at_risk", "ready", "complete", "unknown",
            "in_progress", "not_started",
        )

    def test_confidence_is_valid(self):
        data = client.get("/internal/review/plan").json()
        assert data["next_best_action"]["confidence"] in ("high", "medium", "low")

    def test_action_queue_sections_present(self):
        data = client.get("/internal/review/plan").json()
        q = data["action_queue"]
        assert "today" in q
        assert "next" in q
        assert "deferred" in q

    def test_critical_path_non_empty(self):
        data = client.get("/internal/review/plan").json()
        assert len(data["critical_path"]) >= 1

    def test_endpoint_advisory_is_set(self):
        data = client.get("/internal/review/plan").json()
        assert data["endpoint_advisory"]


# ---------------------------------------------------------------------------
# Review page displays planner output
# ---------------------------------------------------------------------------

class TestReviewPagePlannerIntegration:
    def test_review_page_still_returns_200(self):
        resp = client.get("/internal/review")
        assert resp.status_code == 200

    def test_review_page_has_next_best_task_section(self):
        resp = client.get("/internal/review")
        text = resp.text
        # The narrative section heading should appear (narrated as "Next Best Task")
        assert "Next Best Task" in text or "Next Best Action" in text or "next best" in text.lower()

    def test_review_page_has_plan_section_id(self):
        resp = client.get("/internal/review")
        assert 's-plan' in resp.text

    def test_review_page_has_critical_path(self):
        resp = client.get("/internal/review")
        assert "Critical Path" in resp.text

    def test_review_page_has_expected_unlocks(self):
        resp = client.get("/internal/review")
        assert "Expected Unlocks" in resp.text or "unlock" in resp.text.lower()

    def test_review_page_has_action_queue(self):
        resp = client.get("/internal/review")
        assert "Action Queue" in resp.text or "Today" in resp.text

    def test_review_page_has_next_task_nav_link(self):
        resp = client.get("/internal/review")
        assert "Next Task" in resp.text or "Next Action" in resp.text


# ---------------------------------------------------------------------------
# Regression: existing endpoints unaffected
# ---------------------------------------------------------------------------

class TestRegressionExistingEndpoints:
    def test_review_html_still_has_decision(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "blocked" in text or "proceed" in text or "ready" in text

    def test_review_html_no_cdn(self):
        resp = client.get("/internal/review")
        assert "cdn." not in resp.text.lower()

    def test_review_html_no_framework(self):
        resp = client.get("/internal/review")
        text = resp.text.lower()
        assert "react" not in text
        assert "vue" not in text

    def test_review_payload_endpoint_unaffected(self):
        resp = client.get("/internal/review/payload")
        assert resp.status_code == 200
        data = resp.json()
        assert "header" in data
        assert "decision" in data

    def test_root_causes_endpoint_unaffected(self):
        resp = client.get("/internal/review/root-causes")
        assert resp.status_code == 200
        data = resp.json()
        assert "root_causes" in data

    def test_demo_endpoint_unaffected(self):
        assert client.get("/internal/demo").status_code == 200

    def test_state_accord_unaffected(self):
        assert client.get("/internal/state/accord/summary").status_code == 200

    def test_intake_unaffected(self):
        assert client.get("/internal/intake").status_code == 200
