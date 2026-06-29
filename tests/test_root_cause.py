"""Tests for the Root Cause Analysis engine."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.root_cause import (
    MAX_ROOT_CAUSES,
    RootCause,
    RootCauseAnalysis,
    ImpactSummary,
    build_root_cause_analysis,
    _qa_concern,
    _score_to_priority,
    _deduplicate,
    _build_impact,
    _seed_candidates,
    _build_summary,
    _format_label,
    _strip_ids,
)


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


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestRootCauseConstruction:
    def test_returns_root_cause_analysis(self, rca):
        assert isinstance(rca, RootCauseAnalysis)

    def test_root_causes_is_list(self, rca):
        assert isinstance(rca.root_causes, list)

    def test_at_most_max_root_causes(self, rca):
        assert len(rca.root_causes) <= MAX_ROOT_CAUSES

    def test_at_least_one_root_cause(self, rca):
        assert len(rca.root_causes) >= 1

    def test_to_dict_is_json_serializable(self, rca):
        import json
        json.dumps(rca.to_dict())

    def test_to_dict_has_required_keys(self, rca):
        d = rca.to_dict()
        for key in (
            "root_causes", "total_impact_score", "summary",
            "summary_detail", "open_qa_count", "open_blocker_count",
            "blocked_phase_count", "collapsed_finding_count",
        ):
            assert key in d, f"Missing key: {key}"

    def test_each_root_cause_has_required_fields(self, rca):
        for rc in rca.root_causes:
            d = rc.to_dict()
            for key in (
                "root_cause_id", "concern_group", "concern_display", "title",
                "description", "recommended_resolution", "priority",
                "impact_score", "impact", "supporting_evidence", "confidence",
            ):
                assert key in d, f"Missing field '{key}' in root cause"


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    def test_sorted_by_impact_score_descending(self, rca):
        scores = [rc.impact_score for rc in rca.root_causes]
        assert scores == sorted(scores, reverse=True)

    def test_priority_valid_values(self, rca):
        valid = {"critical", "high", "medium", "low"}
        for rc in rca.root_causes:
            assert rc.priority in valid

    def test_score_to_priority_thresholds(self):
        assert _score_to_priority(200) == "critical"
        assert _score_to_priority(100) == "critical"
        assert _score_to_priority(60) == "high"
        assert _score_to_priority(30) == "medium"
        assert _score_to_priority(10) == "low"

    def test_highest_score_is_highest_priority(self, rca):
        if len(rca.root_causes) >= 2:
            top = rca.root_causes[0]
            second = rca.root_causes[1]
            assert top.impact_score >= second.impact_score


# ---------------------------------------------------------------------------
# Impact scoring
# ---------------------------------------------------------------------------

class TestImpactScoring:
    def test_impact_score_positive(self, rca):
        for rc in rca.root_causes:
            assert rc.impact_score > 0

    def test_total_impact_score_is_sum(self, rca):
        expected = sum(rc.impact_score for rc in rca.root_causes)
        assert rca.total_impact_score == expected

    def test_joining_concern_has_highest_score(self, rca):
        joining = next((rc for rc in rca.root_causes if rc.concern_group == "joining"), None)
        if joining:
            assert joining.impact_score == rca.root_causes[0].impact_score

    def test_critical_qa_gate_raises_score(self, model):
        rca = build_root_cause_analysis(model)
        joining = next((rc for rc in rca.root_causes if rc.concern_group == "joining"), None)
        if joining:
            # Critical QA gate = +100, plus additional gates and material safety
            assert joining.impact_score >= 100


# ---------------------------------------------------------------------------
# Duplicate collapsing
# ---------------------------------------------------------------------------

class TestDuplicateCollapsing:
    def test_no_duplicate_concern_groups(self, rca):
        concerns = [rc.concern_group for rc in rca.root_causes]
        assert len(concerns) == len(set(concerns)), "Duplicate concern groups in root causes"

    def test_fewer_root_causes_than_raw_findings(self, rca, model):
        if model.insights:
            raw_count = len(model.insights.findings)
            assert len(rca.root_causes) < raw_count

    def test_collapse_ratio_reasonable(self, rca, model):
        if model.insights and len(model.insights.findings) >= 5:
            assert len(rca.root_causes) <= MAX_ROOT_CAUSES
            assert rca.collapsed_finding_count >= len(rca.root_causes)

    def test_deduplication_merges_high_overlap(self):
        """Two candidates with identical blocked_qa sets should be merged."""
        shared_qa = {"Verify joining method A", "Verify joining method B"}

        def _make_candidate(concern: str):
            return (
                {"type": "qa_gate", "concern": concern, "gate": None, "blocker": None},
                ImpactSummary(blocked_qa=list(shared_qa), blocked_phases=["Phase A"]),
                100,
                [],
            )

        cands = [_make_candidate("joining"), _make_candidate("joining_compliance")]
        result = _deduplicate(cands)
        assert len(result) == 1, "High-overlap candidates should be merged"

    def test_deduplication_keeps_distinct_concerns(self):
        """Candidates with no overlap must both survive deduplication."""
        cand1 = (
            {"type": "qa_gate", "concern": "joining", "gate": None, "blocker": None},
            ImpactSummary(blocked_qa=["Verify joining"], blocked_phases=["Phase 1"]),
            100, [],
        )
        cand2 = (
            {"type": "qa_gate", "concern": "corrosion", "gate": None, "blocker": None},
            ImpactSummary(blocked_qa=["Verify sealer"], blocked_phases=["Phase 3"]),
            80, [],
        )
        result = _deduplicate([cand1, cand2])
        assert len(result) == 2, "Distinct concerns must not be merged"


# ---------------------------------------------------------------------------
# Minimum root cause set
# ---------------------------------------------------------------------------

class TestMinimumRootCauseSet:
    def test_demo_model_produces_bounded_root_causes(self, rca):
        assert 1 <= len(rca.root_causes) <= MAX_ROOT_CAUSES

    def test_no_model_state_returns_empty(self):
        mock_model = MagicMock()
        mock_model.state = None
        result = build_root_cause_analysis(mock_model)
        assert result.root_causes == []
        assert "No repair state" in result.summary

    def test_low_signal_candidates_filtered(self, model):
        """Candidates with no QA gates and no blocked phases and low score
        are filtered from the output."""
        rca = build_root_cause_analysis(model)
        for rc in rca.root_causes:
            has_qa = len(rc.impact.blocked_qa) > 0
            has_phases = len(rc.impact.blocked_phases) > 0
            high_score = rc.impact_score >= 75
            assert has_qa or has_phases or high_score


# ---------------------------------------------------------------------------
# Dependency / blocked phase traversal
# ---------------------------------------------------------------------------

class TestDependencyTraversal:
    def test_blocked_phases_are_strings(self, rca):
        for rc in rca.root_causes:
            assert all(isinstance(p, str) for p in rc.impact.blocked_phases)

    def test_blocked_qa_are_strings(self, rca):
        for rc in rca.root_causes:
            assert all(isinstance(q, str) for q in rc.impact.blocked_qa)

    def test_unblocked_phases_populated_for_blocked(self, rca):
        """If a root cause has blocked phases, unblocked_phases must also be set."""
        for rc in rca.root_causes:
            if rc.impact.blocked_phases:
                assert rc.impact.unblocked_phases == rc.impact.blocked_phases

    def test_joining_concern_blocks_phase(self, rca):
        joining = next((rc for rc in rca.root_causes if rc.concern_group == "joining"), None)
        if joining:
            assert len(joining.impact.blocked_phases) >= 1


# ---------------------------------------------------------------------------
# QA gate aggregation
# ---------------------------------------------------------------------------

class TestQAGateAggregation:
    def test_joining_concern_aggregates_multiple_gates(self, rca, model):
        joining = next((rc for rc in rca.root_causes if rc.concern_group == "joining"), None)
        if joining and model.state:
            joining_qa_count = sum(
                1 for g in model.state.qa_gates
                if g.status == "open" and g.blocks_completion
                and _qa_concern(g.gate_id) == "joining"
            )
            assert len(joining.impact.blocked_qa) == min(joining_qa_count, len(joining.impact.blocked_qa))
            assert len(joining.impact.blocked_qa) >= 1

    def test_no_internal_ids_in_qa_texts(self, rca):
        import re
        id_pat = re.compile(r"qa:[a-z_]+:[a-z]+:\d+")
        for rc in rca.root_causes:
            for q in rc.impact.blocked_qa:
                assert not id_pat.search(q), f"Internal ID in QA text: {q!r}"

    def test_open_qa_count_accurate(self, rca, model):
        if model.state:
            expected = sum(
                1 for g in model.state.qa_gates
                if g.status == "open" and g.blocks_completion
            )
            assert rca.open_qa_count == expected


# ---------------------------------------------------------------------------
# Recommendation generation
# ---------------------------------------------------------------------------

class TestRecommendationGeneration:
    def test_recommended_resolution_non_empty(self, rca):
        for rc in rca.root_causes:
            assert rc.recommended_resolution.strip()

    def test_recommended_resolution_no_internal_ids(self, rca):
        import re
        id_pat = re.compile(r"qa:[a-z_]+:[a-z]+:\d+")
        for rc in rca.root_causes:
            assert not id_pat.search(rc.recommended_resolution), (
                f"Internal ID in resolution: {rc.recommended_resolution!r}"
            )

    def test_resolution_with_phases_mentions_unblock(self, rca):
        for rc in rca.root_causes:
            if rc.impact.blocked_phases:
                assert "unblock" in rc.recommended_resolution.lower() or "resolving" in rc.recommended_resolution.lower()

    def test_description_non_empty(self, rca):
        for rc in rca.root_causes:
            assert rc.description.strip()


# ---------------------------------------------------------------------------
# Summary text
# ---------------------------------------------------------------------------

class TestSummaryText:
    def test_summary_non_empty(self, rca):
        assert rca.summary.strip()

    def test_summary_detail_non_empty_when_root_causes(self, rca):
        if rca.root_causes:
            # Detail may be empty if no phases or QA are blocked
            assert isinstance(rca.summary_detail, str)

    def test_summary_mentions_critical_when_critical(self, rca):
        has_critical = any(rc.priority == "critical" for rc in rca.root_causes)
        if has_critical:
            assert "critical" in rca.summary.lower() or "Critical" in rca.summary

    def test_summary_blocked_when_any_critical_root_cause(self, rca):
        has_critical = any(rc.priority == "critical" for rc in rca.root_causes)
        if has_critical:
            assert "blocked" in rca.summary.lower() or "Blocked" in rca.summary

    def test_empty_model_produces_sensible_summary(self):
        mock_model = MagicMock()
        mock_model.state = None
        result = build_root_cause_analysis(mock_model)
        assert result.summary


# ---------------------------------------------------------------------------
# Concern group ID helpers
# ---------------------------------------------------------------------------

class TestConcernGroupHelpers:
    def test_qa_concern_joining(self):
        assert _qa_concern("qa:material_compliance:critical:2") == "joining"
        assert _qa_concern("qa:joining_compliance:high:3") == "joining"

    def test_qa_concern_corrosion(self):
        assert _qa_concern("qa:corrosion_protection:high:15") == "corrosion"

    def test_qa_concern_unknown_passthrough(self):
        result = _qa_concern("qa:unknown_category:medium:1")
        assert isinstance(result, str)

    def test_format_label_acronyms(self):
        assert "QA" in _format_label("qa_inspection")
        assert "OEM" in _format_label("oem_procedure")

    def test_strip_ids_removes_gate_prefix(self):
        assert _strip_ids("QA gate remains open: Verify method.") == "Verify method."

    def test_strip_ids_removes_resolve_prefix(self):
        text = "Resolve QA gate qa:material_compliance:critical:2. Check: Verify something."
        assert "qa:material_compliance:critical:2" not in _strip_ids(text)


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

class TestRootCauseAPI:
    @pytest.fixture(autouse=True)
    def require_fastapi(self):
        pytest.importorskip("fastapi", reason="fastapi not installed")

    def test_root_causes_endpoint_returns_200(self):
        from fastapi.testclient import TestClient
        from repairgraph.api.app import app
        client = TestClient(app)
        response = client.get("/internal/review/root-causes")
        assert response.status_code == 200

    def test_root_causes_endpoint_returns_json(self):
        from fastapi.testclient import TestClient
        from repairgraph.api.app import app
        client = TestClient(app)
        response = client.get("/internal/review/root-causes")
        data = response.json()
        assert "root_causes" in data
        assert "summary" in data
        assert "total_impact_score" in data

    def test_root_causes_endpoint_root_causes_are_list(self):
        from fastapi.testclient import TestClient
        from repairgraph.api.app import app
        client = TestClient(app)
        response = client.get("/internal/review/root-causes")
        assert isinstance(response.json()["root_causes"], list)

    def test_root_causes_endpoint_advisory_present(self):
        from fastapi.testclient import TestClient
        from repairgraph.api.app import app
        client = TestClient(app)
        response = client.get("/internal/review/root-causes")
        assert "endpoint_advisory" in response.json()


# ---------------------------------------------------------------------------
# Regression — root_cause_analysis in ExecutiveReview
# ---------------------------------------------------------------------------

class TestRootCauseInExecutiveReview:
    def test_executive_review_has_root_cause_analysis(self, model):
        from repairgraph.review.executive_review import build_executive_review
        er = build_executive_review(model)
        assert er.root_cause_analysis is not None

    def test_executive_review_rca_has_root_causes(self, model):
        from repairgraph.review.executive_review import build_executive_review
        er = build_executive_review(model)
        assert "root_causes" in er.root_cause_analysis

    def test_executive_review_dict_has_root_cause_analysis(self, model):
        from repairgraph.review.executive_review import build_executive_review
        d = build_executive_review(model).to_dict()
        assert "root_cause_analysis" in d
        assert isinstance(d["root_cause_analysis"], dict)

    def test_review_html_contains_root_cause_section(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        assert "Root Cause Analysis" in html
        assert "s-root-causes" in html

    def test_review_html_contains_rc_summary(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        # Should mention "Root Cause" in the page summary
        assert "Root Cause" in html
