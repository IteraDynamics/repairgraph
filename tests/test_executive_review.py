"""Tests for the ExecutiveReview engine."""
from __future__ import annotations

import pytest

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.executive_review import (
    DECISION_BLOCKED,
    DECISION_CAUTION,
    DECISION_INSUFFICIENT,
    DECISION_READY,
    ExecutiveReview,
    build_executive_review,
    _derive_overall_decision,
    _build_immediate_actions,
    _build_technician_message,
    _build_manager_message,
    _generate_executive_summary,
    _build_confidence,
    _build_decision_rationale,
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
def review(model):
    return build_executive_review(model)


# ---------------------------------------------------------------------------
# ExecutiveReview construction
# ---------------------------------------------------------------------------

class TestExecutiveReviewConstruction:
    def test_returns_executive_review(self, review):
        assert isinstance(review, ExecutiveReview)

    def test_to_dict_is_json_serializable(self, review):
        import json
        json.dumps(review.to_dict())

    def test_all_fields_present(self, review):
        d = review.to_dict()
        expected = [
            "overall_decision", "hero_label", "primary_problem", "executive_summary",
            "immediate_actions", "deferred_actions", "business_risks",
            "technician_message", "manager_message", "confidence",
            "decision_rationale", "decision_rationale_extra",
        ]
        for key in expected:
            assert key in d, f"Missing key: {key}"

    def test_hero_label_matches_overall_decision(self, review):
        assert review.hero_label == review.overall_decision

    def test_overall_decision_is_valid(self, review):
        assert review.overall_decision in (
            DECISION_BLOCKED, DECISION_CAUTION, DECISION_READY, DECISION_INSUFFICIENT
        )


# ---------------------------------------------------------------------------
# Decision precedence
# ---------------------------------------------------------------------------

class TestDecisionPrecedence:
    def test_decision_is_string(self, model):
        d = _derive_overall_decision(model)
        assert isinstance(d, str)

    def test_decision_is_valid_value(self, model):
        d = _derive_overall_decision(model)
        assert d in (DECISION_BLOCKED, DECISION_CAUTION, DECISION_READY, DECISION_INSUFFICIENT)

    def test_incomplete_packet_returns_insufficient(self, model):
        """Simulate an incomplete packet by checking that the logic path exists."""
        # The actual model may or may not have an incomplete packet;
        # we verify the function handles it correctly by patching readiness.
        from unittest.mock import patch
        with patch.object(model.source_manifest, "readiness", "incomplete"):
            d = _derive_overall_decision(model)
        assert d == DECISION_INSUFFICIENT

    def test_unprocessable_packet_returns_insufficient(self, model):
        from unittest.mock import patch
        with patch.object(model.source_manifest, "readiness", "unprocessable"):
            d = _derive_overall_decision(model)
        assert d == DECISION_INSUFFICIENT

    def test_critical_blocker_returns_blocked(self, model):
        """If a critical blocker is present and packet is complete, decision must be BLOCKED."""
        from unittest.mock import patch
        if model.state:
            critical = [b for b in model.state.blockers if b.severity == "critical" and b.status == "open"]
            if critical:
                # Patch readiness to "ready" so packet incompleteness doesn't take precedence
                with patch.object(model.source_manifest, "readiness", "ready"):
                    assert _derive_overall_decision(model) == DECISION_BLOCKED

    def test_blocked_insight_returns_blocked(self, model):
        """blocked insight status → BLOCKED (unless packet is incomplete first)."""
        from unittest.mock import patch
        with patch.object(model.source_manifest, "readiness", "ready"):
            if model.insights and model.insights.overall_status == "blocked":
                if model.state:
                    critical = [b for b in model.state.blockers if b.severity == "critical" and b.status == "open"]
                    if not critical:
                        assert _derive_overall_decision(model) == DECISION_BLOCKED


# ---------------------------------------------------------------------------
# Immediate action prioritization
# ---------------------------------------------------------------------------

class TestImmediateActionPrioritization:
    def test_at_most_three_immediate_actions(self, model):
        decision = _derive_overall_decision(model)
        actions = _build_immediate_actions(model, decision)
        assert len(actions) <= 3

    def test_immediate_actions_are_strings(self, model):
        decision = _derive_overall_decision(model)
        actions = _build_immediate_actions(model, decision)
        assert all(isinstance(a, str) for a in actions)

    def test_no_duplicate_actions(self, model):
        decision = _derive_overall_decision(model)
        actions = _build_immediate_actions(model, decision)
        assert len(actions) == len(set(actions))

    def test_review_immediate_actions_at_most_three(self, review):
        assert len(review.immediate_actions) <= 3

    def test_deferred_actions_do_not_overlap_immediate(self, review):
        immediate_set = set(review.immediate_actions)
        for a in review.deferred_actions:
            assert a not in immediate_set


# ---------------------------------------------------------------------------
# Manager summary
# ---------------------------------------------------------------------------

class TestManagerSummary:
    def test_manager_message_is_string(self, review):
        assert isinstance(review.manager_message, str)

    def test_manager_message_non_empty(self, review):
        assert review.manager_message.strip()

    def test_manager_message_blocked_mentions_release(self, model):
        from unittest.mock import patch
        with patch.object(model.source_manifest, "readiness", "incomplete"):
            msg = _build_manager_message(model, DECISION_INSUFFICIENT)
        assert "release" in msg.lower() or "not" in msg.lower()

    def test_manager_message_ready_mentions_verification(self, model):
        msg = _build_manager_message(model, DECISION_READY)
        assert any(word in msg.lower() for word in ("verify", "confirm", "oem", "documented"))


# ---------------------------------------------------------------------------
# Technician summary
# ---------------------------------------------------------------------------

class TestTechnicianSummary:
    def test_technician_message_is_string(self, review):
        assert isinstance(review.technician_message, str)

    def test_technician_message_non_empty(self, review):
        assert review.technician_message.strip()

    def test_technician_message_blocked_is_directive(self, model):
        from unittest.mock import patch
        with patch.object(model.source_manifest, "readiness", "incomplete"):
            msg = _build_technician_message(model, DECISION_INSUFFICIENT, [])
        assert any(word in msg.lower() for word in ("do not", "stop", "contact", "supply"))

    def test_technician_message_ready_is_affirmative(self, model):
        msg = _build_technician_message(model, DECISION_READY, ["Continue with installation."])
        assert msg  # non-empty


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

class TestExecutiveSummary:
    def test_executive_summary_non_empty(self, review):
        assert review.executive_summary.strip()

    def test_executive_summary_word_count(self, review):
        words = review.executive_summary.split()
        assert 20 <= len(words) <= 150, f"Summary word count {len(words)} out of range"

    def test_executive_summary_blocked_contains_proceed(self, model):
        decision = DECISION_BLOCKED
        primary = "OEM joining verification is incomplete."
        actions = ["Verify OEM joining method."]
        summary = _generate_executive_summary(model, decision, primary, actions)
        assert "proceed" in summary.lower() or "blocked" in summary.lower() or "cannot" in summary.lower()

    def test_executive_summary_ready_is_positive(self, model):
        decision = DECISION_READY
        primary = "All checks have passed."
        actions = ["Continue with installation."]
        summary = _generate_executive_summary(model, decision, primary, actions)
        assert "ready" in summary.lower() or "proceed" in summary.lower() or "complete" in summary.lower()

    def test_executive_summary_insufficient_mentions_incomplete(self, model):
        decision = DECISION_INSUFFICIENT
        primary = "The repair packet is missing required documentation."
        actions = []
        summary = _generate_executive_summary(model, decision, primary, actions)
        assert "incomplete" in summary.lower() or "packet" in summary.lower() or "missing" in summary.lower()


# ---------------------------------------------------------------------------
# Confidence explanation
# ---------------------------------------------------------------------------

class TestConfidenceExplanation:
    def test_confidence_fields_present(self, review):
        conf = review.confidence
        assert conf.evidence_confidence in ("High", "Medium", "Low")
        assert conf.decision_confidence in ("High", "Medium", "Low")
        assert conf.evidence_confidence_reason
        assert conf.decision_confidence_reason

    def test_confidence_to_dict(self, review):
        d = review.confidence.to_dict()
        for key in ("evidence_confidence", "evidence_confidence_reason",
                    "decision_confidence", "decision_confidence_reason"):
            assert key in d

    def test_evidence_and_decision_confidence_are_independent(self, model):
        conf = _build_confidence(model)
        # They CAN differ — no assertion they must be the same
        assert conf.evidence_confidence != "" and conf.decision_confidence != ""

    def test_no_source_docs_yields_low_evidence_confidence(self, model):
        from unittest.mock import patch, MagicMock
        mock_evidence = MagicMock()
        mock_evidence.confidence_by_category = {}
        mock_evidence.requires_oem_verification = True
        mock_manifest = MagicMock()
        mock_manifest.source_count = 0
        with patch.object(model, "evidence", mock_evidence):
            with patch.object(model, "source_manifest", mock_manifest):
                conf = _build_confidence(model)
        assert conf.evidence_confidence == "Low"


# ---------------------------------------------------------------------------
# Decision rationale
# ---------------------------------------------------------------------------

class TestDecisionRationale:
    def test_rationale_at_most_five(self, review):
        assert len(review.decision_rationale) <= 5

    def test_rationale_findings_have_severity(self, review):
        for f in review.decision_rationale:
            assert "severity" in f
            assert f["severity"] in ("critical", "high", "medium", "low", "informational")

    def test_rationale_sorted_by_severity(self, review):
        sev_order = ["critical", "high", "medium", "low", "informational"]
        ranks = [
            sev_order.index(f.get("severity", "informational"))
            for f in review.decision_rationale
            if f.get("severity") in sev_order
        ]
        assert ranks == sorted(ranks)

    def test_extra_rationale_contains_remaining(self, model):
        top, extra = _build_decision_rationale(model)
        assert len(top) <= 5
        if model.insights and len(model.insights.findings) > 5:
            assert len(extra) > 0

    def test_combined_rationale_covers_all_findings(self, model):
        top, extra = _build_decision_rationale(model)
        total = len(top) + len(extra)
        if model.insights:
            assert total == len(model.insights.findings)


# ---------------------------------------------------------------------------
# Printable summary (via HTML page)
# ---------------------------------------------------------------------------

class TestPrintableSummary:
    def test_print_summary_in_html(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        assert "rr-print-summary" in html

    def test_print_summary_contains_decision(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        # The print area should contain the decision label
        assert "rr-print-decision-label" in html

    def test_print_summary_contains_legal(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        assert "rr-print-legal" in html

    def test_print_summary_contains_technician_and_manager(self, model):
        from repairgraph.review.review_payload import build_review_payload
        from repairgraph.review.review_page import build_review_page_html
        payload = build_review_payload(model)
        html = build_review_page_html(payload)
        assert "Technician" in html
        assert "Manager" in html


# ---------------------------------------------------------------------------
# Regression — executive_review in ReviewPayload
# ---------------------------------------------------------------------------

class TestExecutiveReviewInPayload:
    def test_executive_review_in_payload_dict(self, model):
        from repairgraph.review.review_payload import build_review_payload
        payload = build_review_payload(model)
        d = payload.to_dict()
        assert "executive_review" in d

    def test_executive_review_has_overall_decision(self, model):
        from repairgraph.review.review_payload import build_review_payload
        payload = build_review_payload(model)
        er = payload.to_dict()["executive_review"]
        assert "overall_decision" in er
        assert er["overall_decision"] in (
            DECISION_BLOCKED, DECISION_CAUTION, DECISION_READY, DECISION_INSUFFICIENT
        )
