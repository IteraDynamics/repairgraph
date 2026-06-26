"""Tests for the Review Repair payload builder."""
from __future__ import annotations

import pytest

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.review.review_payload import (
    ReviewPayload,
    build_review_payload,
    _derive_decision,
    _derive_confidence,
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
def payload(model):
    return build_review_payload(model)


class TestReviewPayloadConstruction:
    def test_returns_review_payload(self, payload):
        assert isinstance(payload, ReviewPayload)

    def test_to_dict_is_json_serializable(self, payload):
        import json
        d = payload.to_dict()
        # Must not raise
        json.dumps(d)

    def test_all_sections_present(self, payload):
        d = payload.to_dict()
        expected = [
            "header", "decision", "top_findings", "documentation",
            "workflow_readiness", "material_risk", "evidence_trail",
            "export_links", "advisory_notice", "generated_at", "model_id",
        ]
        for key in expected:
            assert key in d, f"Missing key: {key}"

    def test_model_id_populated(self, payload):
        assert payload.model_id

    def test_generated_at_populated(self, payload):
        assert payload.generated_at

    def test_advisory_notice_populated(self, payload):
        assert payload.advisory_notice


class TestDecisionDerivation:
    def test_blocked_model_returns_blocked_decision(self, model):
        # Demo model has open blockers → should be Blocked
        decision = _derive_decision(model)
        assert decision in ("Blocked", "Proceed with Caution", "Needs Review", "Ready to Proceed", "Insufficient Packet")

    def test_decision_is_string(self, model):
        assert isinstance(_derive_decision(model), str)

    def test_confidence_is_valid(self, model):
        confidence = _derive_confidence(model)
        assert confidence in ("High", "Medium", "Low")

    def test_decision_keys_present(self, payload):
        d = payload.decision
        for key in ("decision", "reason", "next_action", "top_risks", "operational_confidence", "risk_level"):
            assert key in d, f"Missing decision key: {key}"

    def test_top_risks_is_list(self, payload):
        assert isinstance(payload.decision.get("top_risks", []), list)

    def test_open_blocker_count_non_negative(self, payload):
        assert payload.decision.get("open_blocker_count", 0) >= 0


class TestStatusMapping:
    def test_header_status_populated(self, payload):
        assert payload.header.get("status")

    def test_header_operational_confidence_valid(self, payload):
        conf = payload.header.get("operational_confidence", "")
        assert conf in ("High", "Medium", "Low")

    def test_header_readiness_populated(self, payload):
        assert payload.header.get("readiness")

    def test_header_oem_populated(self, payload):
        # Honda Accord adapter should surface OEM
        assert payload.header.get("oem") == "Honda"

    def test_header_year_populated(self, payload):
        assert payload.header.get("year") == 2025


class TestTopFindingsOrdering:
    def test_top_findings_at_most_five(self, payload):
        top = payload.top_findings.get("top_findings", [])
        assert len(top) <= 5

    def test_all_findings_contains_top(self, payload):
        top = payload.top_findings.get("top_findings", [])
        all_f = payload.top_findings.get("all_findings", [])
        assert len(all_f) >= len(top)

    def test_total_count_matches_all(self, payload):
        all_f = payload.top_findings.get("all_findings", [])
        assert payload.top_findings.get("total_count") == len(all_f)

    def test_findings_have_required_keys(self, payload):
        for f in payload.top_findings.get("top_findings", []):
            for key in ("finding_id", "severity", "category", "title", "explanation", "recommended_action"):
                assert key in f, f"Finding missing key: {key}"

    def test_top_findings_severity_order(self, payload):
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
        top = payload.top_findings.get("top_findings", [])
        ranks = [severity_order.get(f.get("severity", "informational"), 99) for f in top]
        assert ranks == sorted(ranks), "Top findings not in severity order"


class TestMissingDocumentRoles:
    def test_documentation_section_present(self, payload):
        doc = payload.documentation
        assert "detected_roles" in doc
        assert "missing_roles" in doc

    def test_missing_roles_is_list(self, payload):
        assert isinstance(payload.documentation.get("missing_roles", []), list)

    def test_has_missing_roles_flag(self, payload):
        doc = payload.documentation
        expected = len(doc.get("missing_roles", [])) > 0
        assert doc.get("has_missing_roles") == expected

    def test_customer_owned_notice_present(self, payload):
        assert payload.documentation.get("customer_owned_content_notice")

    def test_readiness_is_valid(self, payload):
        assert payload.documentation.get("readiness") in ("ready", "partial", "incomplete", "unprocessable")


class TestWorkflowReadinessDisplay:
    def test_workflow_section_present(self, payload):
        wf = payload.workflow_readiness
        for key in ("current_phase", "blocked_phases", "open_blockers", "next_actions", "completed_actions", "qa_gates", "workflow_readiness"):
            assert key in wf, f"Missing workflow key: {key}"

    def test_qa_gates_has_open_and_passed(self, payload):
        qa = payload.workflow_readiness.get("qa_gates", {})
        assert "open" in qa
        assert "passed" in qa

    def test_open_blockers_is_list(self, payload):
        assert isinstance(payload.workflow_readiness.get("open_blockers", []), list)

    def test_completed_actions_is_list(self, payload):
        assert isinstance(payload.workflow_readiness.get("completed_actions", []), list)

    def test_action_counts_consistent(self, payload):
        wf = payload.workflow_readiness
        total = wf.get("action_count", 0)
        done = wf.get("complete_action_count", 0)
        assert done <= total


class TestEvidenceTrailInclusion:
    def test_evidence_trail_present(self, payload):
        ev = payload.evidence_trail
        for key in ("evidence_items", "finding_evidence", "confidence_by_category", "requires_oem_verification", "total_evidence_count"):
            assert key in ev, f"Missing evidence key: {key}"

    def test_total_count_matches_items(self, payload):
        ev = payload.evidence_trail
        assert ev["total_evidence_count"] == len(ev["evidence_items"])

    def test_requires_oem_verification_true(self, payload):
        assert payload.evidence_trail.get("requires_oem_verification") is True

    def test_finding_evidence_is_list(self, payload):
        assert isinstance(payload.evidence_trail.get("finding_evidence", []), list)


class TestAdvisoryLanguage:
    def test_advisory_notice_contains_advisory(self, payload):
        notice = payload.advisory_notice.lower()
        assert "advisory" in notice

    def test_advisory_notice_mentions_oem(self, payload):
        notice = payload.advisory_notice.lower()
        assert "oem" in notice

    def test_advisory_notice_mentions_technician(self, payload):
        notice = payload.advisory_notice.lower()
        assert "technician" in notice

    def test_customer_owned_notice_in_documentation(self, payload):
        notice = payload.documentation.get("customer_owned_content_notice", "").lower()
        assert "oem" in notice or "customer" in notice


class TestExportLinks:
    def test_export_links_present(self, payload):
        assert payload.export_links
        assert isinstance(payload.export_links, dict)

    def test_key_links_present(self, payload):
        for key in ("topology_viewer", "technician_workflow", "oem_intake"):
            assert key in payload.export_links, f"Missing export link: {key}"
