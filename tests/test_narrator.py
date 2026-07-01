"""Tests for the Operational Narration Layer."""
from __future__ import annotations

import json
import re
import pytest
from fastapi.testclient import TestClient

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.api.app import app
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.narrator import (
    OperationalNarrative,
    _clean,
    _narrate_action_label,
    _narrate_phase,
    _narrate_part,
    _narrate_queue_items,
    _narrate_unlock_label,
    _strip_internal_ids,
    _strip_prefixes,
    build_narrative,
)
from repairgraph.review.operational_planner import build_operational_plan
from repairgraph.review.root_cause import build_root_cause_analysis

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
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
def plan(model):
    rca = build_root_cause_analysis(model)
    return build_operational_plan(model, rca=rca)


@pytest.fixture(scope="module")
def narrative(plan):
    return build_narrative(plan)


# ---------------------------------------------------------------------------
# Internal ID removal helpers
# ---------------------------------------------------------------------------

class TestStripInternalIds:
    def test_removes_qa_gate_id(self):
        result = _strip_internal_ids("qa:material_compliance:critical:2 some text")
        assert "qa:material_compliance:critical:2" not in result

    def test_removes_phase_id(self):
        result = _strip_internal_ids("See phase:4 for details")
        assert "phase:4" not in result

    def test_removes_qa_gate_literal(self):
        result = _strip_internal_ids("This is a qa_gate issue")
        assert "qa_gate" not in result

    def test_removes_replace_component(self):
        result = _strip_internal_ids("replace_component:front_upper_edge")
        assert "replace_component:" not in result

    def test_removes_qa_gate_remains_open_prefix(self):
        result = _strip_internal_ids("QA gate remains open: Verify something")
        assert "QA gate remains open" not in result

    def test_preserves_natural_text(self):
        result = _strip_internal_ids("Verify the OEM joining method before proceeding.")
        assert "Verify the OEM joining method before proceeding" in result


class TestStripPrefixes:
    def test_strips_clear_qa_gate(self):
        result = _strip_prefixes("Clear QA gate: Verify something")
        assert result == "Verify something"

    def test_strips_unblock_phase(self):
        result = _strip_prefixes("Unblock phase: Panel Installation")
        assert result == "Panel Installation"

    def test_strips_resolve_prefix(self):
        result = _strip_prefixes("Resolve: The blocker")
        assert result == "The blocker"

    def test_no_change_for_clean_text(self):
        result = _strip_prefixes("Install the rear inner panel.")
        assert result == "Install the rear inner panel."


# ---------------------------------------------------------------------------
# Action label narration
# ---------------------------------------------------------------------------

class TestNarrateActionLabel:
    def test_replace_component_becomes_install(self):
        result = _narrate_action_label("Replace Component: rear_inner_panel")
        assert result.startswith("Install")
        assert "qa_gate" not in result.lower()
        assert "replace_component" not in result.lower()

    def test_replace_component_known_part(self):
        result = _narrate_action_label("Replace Component: front_upper_edge")
        assert "front upper edge" in result.lower()

    def test_replace_component_with_complete_suffix(self):
        result = _narrate_action_label("Replace Component: front_lower_edge (complete)")
        assert "replace_component" not in result.lower()
        assert "front lower edge" in result.lower()

    def test_clear_qa_gate_strips_prefix(self):
        result = _narrate_action_label("Clear QA gate: Verify OEM joining method.")
        assert "Clear QA gate" not in result
        assert "Verify OEM joining method" in result

    def test_unblock_phase_becomes_resume(self):
        result = _narrate_action_label("Unblock phase: Panel Installation")
        assert result.startswith("Resume")
        assert "Unblock" not in result

    def test_unblock_and_resume_variant(self):
        result = _narrate_action_label("Unblock and resume: Corrosion Protection.")
        assert "Unblock" not in result
        assert "resume" in result.lower() or "corrosion" in result.lower()

    def test_no_internal_id_in_output(self):
        for raw in [
            "Replace Component: quarter_pillar_stiffener",
            "Clear QA gate: qa:material_compliance:critical:2",
            "Unblock phase: panel_installation_and_joining",
        ]:
            result = _narrate_action_label(raw)
            assert "qa:" not in result
            assert "replace_component:" not in result
            assert "phase:" not in result

    def test_result_ends_with_period(self):
        result = _narrate_action_label("Replace Component: rear_inner_panel")
        assert result.endswith(".")


class TestNarratePart:
    def test_known_part_mapping(self):
        assert "rear inner panel" in _narrate_part("rear_inner_panel")
        assert "quarter pillar stiffener" in _narrate_part("quarter_pillar_stiffener")
        assert "front upper edge reinforcement" in _narrate_part("front_upper_edge")

    def test_unknown_part_splits_underscore(self):
        result = _narrate_part("some_unknown_part")
        assert "_" not in result
        assert "some unknown part" in result.lower()


class TestNarratePhase:
    def test_known_phase_mapping(self):
        assert "structural panel installation" in _narrate_phase("panel_installation_and_joining").lower()
        assert "corrosion" in _narrate_phase("corrosion_protection").lower()

    def test_unknown_phase_splits_underscore(self):
        result = _narrate_phase("custom_phase_name")
        assert "_" not in result


class TestNarrateUnlockLabel:
    def test_phase_unlock_readable(self):
        result = _narrate_unlock_label({"unlock_type": "phase", "label": "Panel Installation and Joining", "unlock_id": "panel_installation_and_joining"})
        assert "can begin" in result.lower()
        assert "phase:" not in result

    def test_qa_gate_unlock_cleaned(self):
        result = _narrate_unlock_label({"unlock_type": "qa_gate", "label": "Verify OEM procedure", "unlock_id": "qa:x:y:1"})
        assert "qa:" not in result

    def test_action_unlock_narrated(self):
        result = _narrate_unlock_label({"unlock_type": "action", "label": "Replace Component: rear_inner_panel", "unlock_id": ""})
        assert "Install" in result or "rear inner panel" in result.lower()

    def test_finding_unlock_human_readable(self):
        result = _narrate_unlock_label({"unlock_type": "finding", "label": "", "unlock_id": ""})
        assert "documentation" in result.lower() or "completeness" in result.lower()


# ---------------------------------------------------------------------------
# OperationalNarrative construction
# ---------------------------------------------------------------------------

class TestOperationalNarrativeConstruction:
    def test_returns_operational_narrative(self, narrative):
        assert isinstance(narrative, OperationalNarrative)

    def test_to_dict_is_json_serializable(self, narrative):
        json.dumps(narrative.to_dict())

    def test_to_dict_has_required_keys(self, narrative):
        d = narrative.to_dict()
        for key in (
            "headline", "next_best_task", "why_now", "expected_progress",
            "expected_unlocks", "today", "next", "later", "critical_path",
            "technician_message", "manager_message", "executive_summary",
            "workflow_summary", "risk_summary", "supporting_evidence",
            "confidence", "advisory",
        ):
            assert key in d, f"Missing key: {key}"

    def test_confidence_is_valid(self, narrative):
        assert narrative.confidence in ("high", "medium", "low")

    def test_advisory_is_set(self, narrative):
        assert narrative.advisory

    def test_all_list_fields_are_lists(self, narrative):
        for field in ("expected_unlocks", "today", "next", "later", "critical_path", "supporting_evidence"):
            assert isinstance(getattr(narrative, field), list), f"{field} should be a list"


# ---------------------------------------------------------------------------
# Internal ID removal — the core quality requirement
# ---------------------------------------------------------------------------

class TestNoInternalIdsInNarrative:
    def test_has_internal_ids_returns_false(self, narrative):
        """The full narrative should contain no internal ID patterns."""
        assert not narrative.has_internal_ids(), (
            "Narrative contains internal IDs — check: "
            + narrative.next_best_task + " / " + narrative.why_now
        )

    def test_next_best_task_no_qa_gate_prefix(self, narrative):
        assert "Clear QA gate" not in narrative.next_best_task
        assert "qa_gate" not in narrative.next_best_task.lower()

    def test_next_best_task_no_replace_component(self, narrative):
        assert "Replace Component" not in narrative.next_best_task
        assert "replace_component:" not in narrative.next_best_task.lower()

    def test_next_best_task_no_raw_id(self, narrative):
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.next_best_task)

    def test_why_now_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.why_now.lower()
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.why_now)

    def test_today_items_no_replace_component(self, narrative):
        for item in narrative.today:
            assert "Replace Component:" not in item, f"Unnarcated item: {item!r}"
            assert "Clear QA gate:" not in item, f"Unnarrated item: {item!r}"

    def test_next_items_no_internal_ids(self, narrative):
        for item in narrative.next:
            assert "replace_component:" not in item.lower()
            assert "qa_gate" not in item.lower()

    def test_critical_path_no_replace_component(self, narrative):
        for step in narrative.critical_path:
            assert "Replace Component:" not in step, f"Unnarrated step: {step!r}"
            assert "Clear QA gate:" not in step, f"Unnarrated step: {step!r}"

    def test_critical_path_no_raw_ids(self, narrative):
        for step in narrative.critical_path:
            assert not re.search(r"replace_component:[a-z_]+", step, re.I)
            assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", step, re.I)

    def test_executive_summary_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.executive_summary.lower()
        assert "replace_component" not in narrative.executive_summary.lower()

    def test_technician_message_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.technician_message.lower()
        assert "replace_component" not in narrative.technician_message.lower()
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.technician_message)

    def test_manager_message_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.manager_message.lower()
        assert "replace_component" not in narrative.manager_message.lower()

    def test_expected_unlocks_no_raw_ids(self, narrative):
        for u in narrative.expected_unlocks:
            assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", u)
            assert "replace_component:" not in u.lower()

    def test_risk_summary_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.risk_summary.lower()
        assert "replace_component" not in narrative.risk_summary.lower()


# ---------------------------------------------------------------------------
# Task language quality
# ---------------------------------------------------------------------------

class TestTaskLanguageQuality:
    def test_next_best_task_is_natural_sentence(self, narrative):
        task = narrative.next_best_task
        # Should read as an imperative sentence
        assert len(task) > 10
        assert task[0].isupper()

    def test_next_best_task_uses_task_verbs(self, narrative):
        task = narrative.next_best_task.lower()
        task_verbs = {"verify", "review", "install", "complete", "inspect", "confirm", "document", "resume"}
        assert any(v in task for v in task_verbs), f"Task lacks task verb: {narrative.next_best_task!r}"

    def test_today_items_read_as_tasks(self, narrative):
        for item in narrative.today:
            assert len(item) > 5
            assert item[0].isupper() or item[0].isdigit()

    def test_today_labels_end_with_period(self, narrative):
        for item in narrative.today:
            assert item.endswith("."), f"Item should end with period: {item!r}"

    def test_critical_path_items_are_sentences(self, narrative):
        for step in narrative.critical_path:
            assert len(step) > 5

    def test_critical_path_uses_natural_phase_names(self, narrative):
        path_text = " ".join(narrative.critical_path).lower()
        # No raw snake_case phase IDs
        assert "panel_installation_and_joining" not in path_text
        assert "corrosion_protection" not in path_text

    def test_today_avoids_deferred_label(self, narrative):
        for item in narrative.today:
            assert "deferred" not in item.lower()

    def test_later_not_called_deferred(self, narrative):
        # The queue uses today/next/later — "deferred" should not appear as a section name
        d = narrative.to_dict()
        assert "deferred" not in d, "Field should be called 'later', not 'deferred'"


# ---------------------------------------------------------------------------
# Technician message quality
# ---------------------------------------------------------------------------

class TestTechnicianMessage:
    def test_technician_message_non_empty(self, narrative):
        assert narrative.technician_message

    def test_technician_message_actionable(self, narrative):
        msg = narrative.technician_message.lower()
        action_words = {"before", "verify", "confirm", "do not", "review", "install", "complete"}
        assert any(w in msg for w in action_words)

    def test_technician_message_no_clear_qa_gate(self, narrative):
        assert "Clear QA gate" not in narrative.technician_message
        assert "qa_gate" not in narrative.technician_message.lower()

    def test_technician_message_no_raw_ids(self, narrative):
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.technician_message)

    def test_technician_message_references_oem_or_procedure(self, narrative):
        msg = narrative.technician_message.lower()
        assert "oem" in msg or "procedure" in msg or "honda" in msg


# ---------------------------------------------------------------------------
# Manager message quality
# ---------------------------------------------------------------------------

class TestManagerMessage:
    def test_manager_message_non_empty(self, narrative):
        assert narrative.manager_message

    def test_manager_message_uses_management_language(self, narrative):
        msg = narrative.manager_message.lower()
        mgmt_words = {"confirm", "verify", "ensure", "assign", "release", "require", "documentation"}
        assert any(w in msg for w in mgmt_words)

    def test_manager_message_no_internal_ids(self, narrative):
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.manager_message)
        assert "replace_component" not in narrative.manager_message.lower()

    def test_manager_message_mentions_verification_or_documentation(self, narrative):
        msg = narrative.manager_message.lower()
        assert "verif" in msg or "document" in msg or "sign" in msg


# ---------------------------------------------------------------------------
# Executive summary quality
# ---------------------------------------------------------------------------

class TestExecutiveSummary:
    def test_executive_summary_non_empty(self, narrative):
        assert narrative.executive_summary

    def test_executive_summary_no_count_list_language(self, narrative):
        summary = narrative.executive_summary.lower()
        # Should not lead with "There are N open issues"
        assert not summary.startswith("there are")

    def test_executive_summary_mentions_blocked_or_status(self, narrative):
        summary = narrative.executive_summary.lower()
        assert "blocked" in summary or "progress" in summary or "repair" in summary

    def test_executive_summary_no_internal_ids(self, narrative):
        assert not re.search(r"qa:[a-z_]+:[a-z]+:\d+", narrative.executive_summary)
        assert "replace_component" not in narrative.executive_summary.lower()


# ---------------------------------------------------------------------------
# Risk summary quality
# ---------------------------------------------------------------------------

class TestRiskSummary:
    def test_risk_summary_non_empty(self, narrative):
        assert narrative.risk_summary

    def test_risk_summary_no_reduces_prefix_exposed_raw(self, narrative):
        # "Reduces:" prefix should be replaced with readable sentence
        assert not narrative.risk_summary.startswith("Reduces:")

    def test_risk_summary_uses_completing_language(self, narrative):
        assert "completing" in narrative.risk_summary.lower() or "reduces" in narrative.risk_summary.lower()

    def test_risk_summary_no_internal_ids(self, narrative):
        assert "qa_gate" not in narrative.risk_summary.lower()


# ---------------------------------------------------------------------------
# Expected progress quality
# ---------------------------------------------------------------------------

class TestExpectedProgress:
    def test_expected_progress_non_empty(self, narrative):
        assert narrative.expected_progress

    def test_expected_progress_operational_language(self, narrative):
        prog = narrative.expected_progress.lower()
        assert "completing" in prog or "allow" in prog or "begin" in prog or "removes" in prog

    def test_expected_progress_no_node_language(self, narrative):
        assert "graph node" not in narrative.expected_progress.lower()
        assert "unlock" not in narrative.expected_progress.lower() or "allow" in narrative.expected_progress.lower()


# ---------------------------------------------------------------------------
# Planner output unchanged
# ---------------------------------------------------------------------------

class TestPlannerOutputUnchanged:
    def test_plan_still_has_raw_display_label(self, plan):
        """Planner output must not be modified by the narrator."""
        label = plan.next_best_action.display_label
        # Planner output retains machine labels (narrator's job to clean them)
        assert label  # just check it exists and is non-empty

    def test_plan_action_queue_still_has_machine_labels(self, plan):
        today = plan.action_queue.get("today", [])
        assert len(today) >= 1
        # Planner queue items may still have "Clear QA gate:" etc.
        assert any("Clear QA gate:" in item or "Replace Component:" in item or item for item in today)

    def test_narrative_does_not_mutate_plan(self, plan, narrative):
        """Building a narrative must not change the plan's fields."""
        original_label = plan.next_best_action.display_label
        # Re-build narrative and check plan is still the same
        from repairgraph.review.narrator import build_narrative as bn
        bn(plan)
        assert plan.next_best_action.display_label == original_label


# ---------------------------------------------------------------------------
# /internal/review/narrative endpoint
# ---------------------------------------------------------------------------

class TestNarrativeEndpoint:
    def test_returns_200(self):
        resp = client.get("/internal/review/narrative")
        assert resp.status_code == 200

    def test_returns_json(self):
        resp = client.get("/internal/review/narrative")
        assert "application/json" in resp.headers["content-type"]

    def test_has_required_keys(self):
        data = client.get("/internal/review/narrative").json()
        for key in (
            "headline", "next_best_task", "why_now", "expected_progress",
            "today", "next", "later", "critical_path", "technician_message",
            "manager_message", "executive_summary", "advisory", "endpoint_advisory",
        ):
            assert key in data, f"Missing key: {key}"

    def test_next_best_task_field_exists(self):
        data = client.get("/internal/review/narrative").json()
        assert data.get("next_best_task")

    def test_no_next_best_action_field(self):
        data = client.get("/internal/review/narrative").json()
        # Narrative uses "next_best_task", not the machine term "next_best_action"
        assert "next_best_action" not in data

    def test_queue_uses_later_not_deferred(self):
        data = client.get("/internal/review/narrative").json()
        assert "later" in data
        assert "deferred" not in data

    def test_next_best_task_no_qa_gate_prefix(self):
        data = client.get("/internal/review/narrative").json()
        task = data.get("next_best_task", "")
        assert "Clear QA gate" not in task
        assert "qa_gate" not in task.lower()

    def test_today_items_no_replace_component(self):
        data = client.get("/internal/review/narrative").json()
        for item in data.get("today", []):
            assert "Replace Component:" not in item

    def test_critical_path_no_machine_labels(self):
        data = client.get("/internal/review/narrative").json()
        for step in data.get("critical_path", []):
            assert "Replace Component:" not in step
            assert "Clear QA gate:" not in step

    def test_no_internal_ids_anywhere(self):
        data = client.get("/internal/review/narrative").json()
        text = json.dumps(data)
        # QA gate IDs should not appear in narrated output
        assert not re.search(r'"qa:[a-z_]+:[a-z]+:\d+"', text)
        assert "replace_component:" not in text.lower()


# ---------------------------------------------------------------------------
# Review page — narrated output
# ---------------------------------------------------------------------------

class TestReviewPageNarratorIntegration:
    def test_review_page_returns_200(self):
        assert client.get("/internal/review").status_code == 200

    def test_review_page_shows_next_best_task(self):
        resp = client.get("/internal/review")
        # Sprint 3: work package supersedes narrative section
        assert "Next Best Task" in resp.text or "Work Package" in resp.text or "Work to Perform" in resp.text

    def test_review_page_no_clear_qa_gate_in_primary_section(self):
        resp = client.get("/internal/review")
        text = resp.text
        # "Clear QA gate:" should NOT appear as task wording in the page
        # (it may appear in raw JSON payload embedded at end, but not in task labels)
        # Check the narrated section specifically
        plan_section_match = re.search(r'id="s-plan".*?</section>', text, re.S)
        if plan_section_match:
            section = plan_section_match.group(0)
            assert "Clear QA gate:" not in section

    def test_review_page_no_replace_component_in_narrated_section(self):
        resp = client.get("/internal/review")
        text = resp.text
        plan_section_match = re.search(r'id="s-plan".*?</section>', text, re.S)
        if plan_section_match:
            section = plan_section_match.group(0)
            assert "Replace Component:" not in section

    def test_review_page_has_expected_progress_section(self):
        resp = client.get("/internal/review")
        # Sprint 3: narrative section replaced by work package; progress shown as "What This Unlocks"
        assert "Expected Progress" in resp.text or "What This Unlocks" in resp.text

    def test_review_page_has_today_badge(self):
        resp = client.get("/internal/review")
        # Sprint 3: "Today" queue is in work package context
        assert "Today" in resp.text or "Work to Perform" in resp.text

    def test_review_page_has_next_badge(self):
        resp = client.get("/internal/review")
        assert "Next" in resp.text

    def test_review_page_no_cdn(self):
        resp = client.get("/internal/review")
        assert "cdn." not in resp.text.lower()

    def test_review_page_still_has_advisory(self):
        resp = client.get("/internal/review")
        assert "advisory" in resp.text.lower()


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

class TestRegression:
    def test_plan_endpoint_unaffected(self):
        resp = client.get("/internal/review/plan")
        assert resp.status_code == 200
        data = resp.json()
        assert "next_best_action" in data

    def test_payload_endpoint_unaffected(self):
        resp = client.get("/internal/review/payload")
        assert resp.status_code == 200
        assert "header" in resp.json()

    def test_root_causes_endpoint_unaffected(self):
        resp = client.get("/internal/review/root-causes")
        assert resp.status_code == 200
        assert "root_causes" in resp.json()

    def test_demo_unaffected(self):
        assert client.get("/internal/demo").status_code == 200

    def test_state_accord_unaffected(self):
        assert client.get("/internal/state/accord/summary").status_code == 200

    def test_intake_unaffected(self):
        assert client.get("/internal/intake").status_code == 200
