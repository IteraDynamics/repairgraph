"""Tests for individual rule modules."""
import pytest
from repairgraph.state.demo import build_accord_projected_state
from repairgraph.insights.rules import (
    qa_findings, workflow_findings, material_findings,
    compliance_findings, intake_findings, milestone_findings,
)


@pytest.fixture(scope="module")
def accord():
    return build_accord_projected_state()


# ── QA findings ──────────────────────────────────────────────────────────────

def test_critical_qa_open_returns_findings(accord):
    findings = qa_findings.critical_qa_open(accord)
    assert len(findings) >= 1
    for f in findings:
        assert f.severity == "critical"
        assert f.category == "qa"


def test_high_qa_by_category_returns_findings(accord):
    findings = qa_findings.high_qa_open_by_category(accord)
    assert len(findings) >= 1
    for f in findings:
        assert f.severity == "high"


def test_medium_qa_open_no_crash(accord):
    findings = qa_findings.medium_qa_open(accord)
    for f in findings:
        assert f.severity == "medium"


# ── Workflow findings ─────────────────────────────────────────────────────────

def test_blocked_phases_detected(accord):
    findings = workflow_findings.blocked_phases(accord)
    assert len(findings) >= 1
    for f in findings:
        assert f.severity == "high"
        assert f.category == "workflow"


def test_repair_cannot_advance_for_3_blocked(accord):
    blocked = [p for p in accord.phases if p.status == "blocked"]
    if len(blocked) >= 2:
        findings = workflow_findings.repair_cannot_advance(accord)
        assert len(findings) == 1
        assert findings[0].severity == "critical"


def test_critical_blockers_open(accord):
    findings = workflow_findings.critical_blockers_open(accord)
    open_critical = [b for b in accord.blockers if b.severity == "critical" and b.status == "open"]
    assert len(findings) == len(open_critical)


# ── Material findings ─────────────────────────────────────────────────────────

def test_uhss_detected_in_accord(accord):
    findings = material_findings.uhss_detected(accord)
    uhss_zones = [z for z in accord.zones if z.material_classification and z.material_classification.strip().upper() in {"UHSS", "BORON"}]
    if uhss_zones:
        assert len(findings) == 1
        assert findings[0].severity == "high"
    else:
        assert findings == []


def test_hss_detected_in_accord(accord):
    findings = material_findings.hss_detected(accord)
    hss_zones = [z for z in accord.zones if z.material_classification and z.material_classification.strip().upper() == "HSS"]
    if hss_zones:
        assert len(findings) == 1
        assert findings[0].severity == "medium"


def test_joining_verification_required(accord):
    findings = material_findings.joining_verification_required(accord)
    # If UHSS zones and joining QA gates exist, should produce a finding
    uhss = any(z.material_classification and z.material_classification.strip().upper() in {"UHSS", "BORON"} for z in accord.zones)
    joining_gates = any("joining" in g.category.lower() and g.status in ("open", "in_review") for g in accord.qa_gates)
    if uhss and joining_gates:
        assert len(findings) >= 1
        assert findings[0].severity == "high"


# ── Compliance findings ───────────────────────────────────────────────────────

def test_corrosion_phase_blocked(accord):
    findings = compliance_findings.corrosion_protection_blocked(accord)
    corrosion_blocked = any("corrosion" in p.name.lower() and p.status == "blocked" for p in accord.phases)
    if corrosion_blocked:
        assert len(findings) >= 1


def test_calibration_assessment_no_crash(accord):
    findings = compliance_findings.calibration_assessment(accord)
    for f in findings:
        assert f.severity == "medium"
        assert f.category == "compliance"


# ── Intake findings ───────────────────────────────────────────────────────────

def test_missing_critical_roles():
    manifest = {"missing_roles": ["corrosion_protection", "materials"], "files": [], "readiness": "partial"}
    findings = intake_findings.missing_critical_roles(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_missing_important_roles():
    manifest = {"missing_roles": ["calibration", "welding"], "files": [], "readiness": "partial"}
    findings = intake_findings.missing_important_roles(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_intake_readiness_partial():
    manifest = {"readiness": "partial", "missing_roles": [], "files": []}
    findings = intake_findings.intake_readiness_concern(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_intake_readiness_ready_no_finding():
    manifest = {"readiness": "ready", "missing_roles": [], "files": []}
    assert intake_findings.intake_readiness_concern(manifest) == []


def test_low_confidence_files():
    manifest = {
        "files": [{"filename": "test.pdf", "confidence": 0.3}],
        "readiness": "ready", "missing_roles": [],
    }
    findings = intake_findings.low_confidence_classifications(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "low"


def test_conflicting_oem_metadata():
    manifest = {
        "files": [
            {"detected_oem": "Honda", "filename": "a.pdf"},
            {"detected_oem": "Toyota", "filename": "b.pdf"},
        ],
        "readiness": "ready", "missing_roles": [],
    }
    findings = intake_findings.conflicting_oem_metadata(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_no_conflicting_oem_single():
    manifest = {
        "files": [{"detected_oem": "Honda"}, {"detected_oem": "Honda"}],
        "readiness": "ready", "missing_roles": [],
    }
    assert intake_findings.conflicting_oem_metadata(manifest) == []


# ── Milestone findings ────────────────────────────────────────────────────────

def test_completed_actions_present(accord):
    findings = milestone_findings.completed_actions(accord)
    complete_actions = [a for a in accord.actions if a.status == "complete"]
    if complete_actions:
        assert len(findings) == 1
        assert findings[0].severity == "informational"


def test_next_recommended_action(accord):
    if accord.next_recommended_actions:
        findings = milestone_findings.next_recommended_action(accord)
        assert len(findings) == 1
        assert findings[0].severity == "informational"


def test_phases_complete(accord):
    findings = milestone_findings.phases_complete(accord)
    complete_phases = [p for p in accord.phases if p.status == "complete"]
    if complete_phases:
        assert len(findings) == 1
        assert findings[0].severity == "informational"


def test_repair_packet_complete():
    manifest = {
        "readiness": "ready",
        "detected_packet": {"oem": "Honda", "model": "Accord"},
    }
    findings = milestone_findings.repair_packet_complete(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "informational"


def test_repair_packet_not_complete_no_finding():
    manifest = {"readiness": "partial", "detected_packet": {}}
    assert milestone_findings.repair_packet_complete(manifest) == []
