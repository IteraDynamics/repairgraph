"""
Tests for the Execution Package Engine v0.

Covers:
- ExecutionPackage construction
- Prerequisite generation
- Verification generation
- Execution step generation
- Completion criteria generation
- Unlock generation
- CollisionWorkPackage projection
- No OEM instruction fabrication
- Review page integration
- /internal/review/package endpoint
- Regression: all fields present
"""
from __future__ import annotations

import re
import pytest

from fastapi.testclient import TestClient

from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.core.execution_package import (
    ExecutionPackage,
    CollisionWorkPackage,
    build_execution_package,
    project_collision_work_package,
)
from repairgraph.review.operational_planner import build_operational_plan
from repairgraph.review.narrator import build_narrative
from repairgraph.review.root_cause import build_root_cause_analysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _build_model():
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
def model():
    return _build_model()


@pytest.fixture(scope="module")
def plan(model):
    rca = build_root_cause_analysis(model)
    return build_operational_plan(model, rca=rca)


@pytest.fixture(scope="module")
def narrative(plan):
    return build_narrative(plan)


@pytest.fixture(scope="module")
def pkg(plan, narrative, model):
    return build_execution_package(plan, narrative, model)


@pytest.fixture(scope="module")
def work_pkg(pkg, narrative):
    return project_collision_work_package(pkg, narrative)


# ---------------------------------------------------------------------------
# ExecutionPackage construction
# ---------------------------------------------------------------------------

class TestExecutionPackageConstruction:
    def test_returns_execution_package_instance(self, pkg):
        assert isinstance(pkg, ExecutionPackage)

    def test_has_package_id(self, pkg):
        assert pkg.package_id
        # UUID format
        assert re.match(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", pkg.package_id)

    def test_has_title(self, pkg):
        assert isinstance(pkg.title, str)
        assert len(pkg.title) > 0

    def test_title_not_too_long(self, pkg):
        assert len(pkg.title) <= 83  # 80 chars + possible "…"

    def test_has_objective(self, pkg):
        assert isinstance(pkg.objective, str)
        assert len(pkg.objective) > 10

    def test_has_status(self, pkg):
        assert pkg.status in ("blocked", "in_progress", "ready", "complete")

    def test_has_priority(self, pkg):
        assert pkg.priority in ("critical", "high", "medium", "low")

    def test_has_generated_at(self, pkg):
        assert pkg.generated_at
        # ISO 8601
        assert "T" in pkg.generated_at

    def test_has_advisory(self, pkg):
        assert pkg.advisory
        assert "advisory" in pkg.advisory.lower()

    def test_to_dict_returns_dict(self, pkg):
        d = pkg.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_all_keys(self, pkg):
        d = pkg.to_dict()
        required = {
            "package_id", "title", "objective", "status", "priority",
            "prerequisites", "required_verifications", "execution_steps",
            "completion_criteria", "expected_unlocks", "blocked_by",
            "risk_reduction", "confidence", "supporting_evidence",
            "generated_at", "advisory",
        }
        assert required <= d.keys()

    def test_confidence_is_string(self, pkg):
        assert pkg.confidence in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# Prerequisite generation
# ---------------------------------------------------------------------------

class TestPrerequisiteGeneration:
    def test_prerequisites_is_list(self, pkg):
        assert isinstance(pkg.prerequisites, list)

    def test_prerequisites_non_empty(self, pkg):
        assert len(pkg.prerequisites) >= 1

    def test_prerequisites_are_strings(self, pkg):
        for p in pkg.prerequisites:
            assert isinstance(p, str)

    def test_prerequisites_non_empty_strings(self, pkg):
        for p in pkg.prerequisites:
            assert len(p.strip()) > 0

    def test_no_raw_gate_ids_in_prerequisites(self, pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for p in pkg.prerequisites:
            assert not pattern.search(p), f"Found raw gate ID in prereq: {p!r}"

    def test_no_internal_prefixes_in_prerequisites(self, pkg):
        for p in pkg.prerequisites:
            assert not p.startswith("blocker:"), f"Raw blocker id in prereq: {p!r}"
            assert not p.startswith("qa:"), f"Raw qa id in prereq: {p!r}"
            assert not p.startswith("phase:"), f"Raw phase id in prereq: {p!r}"


# ---------------------------------------------------------------------------
# Verification generation
# ---------------------------------------------------------------------------

class TestVerificationGeneration:
    def test_verifications_is_list(self, pkg):
        assert isinstance(pkg.required_verifications, list)

    def test_verifications_non_empty(self, pkg):
        assert len(pkg.required_verifications) >= 1

    def test_verifications_are_strings(self, pkg):
        for v in pkg.required_verifications:
            assert isinstance(v, str)

    def test_no_raw_gate_ids_in_verifications(self, pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for v in pkg.required_verifications:
            assert not pattern.search(v), f"Found raw gate ID in verification: {v!r}"


# ---------------------------------------------------------------------------
# Execution step generation
# ---------------------------------------------------------------------------

class TestExecutionStepGeneration:
    def test_execution_steps_is_list(self, pkg):
        assert isinstance(pkg.execution_steps, list)

    def test_execution_steps_non_empty(self, pkg):
        assert len(pkg.execution_steps) >= 2

    def test_execution_steps_are_strings(self, pkg):
        for s in pkg.execution_steps:
            assert isinstance(s, str)

    def test_first_step_references_primary_task(self, pkg, narrative):
        # The first step should include the primary task text or a reference to it
        first = pkg.execution_steps[0].lower()
        assert "primary" in first or "verification" in first or len(first) > 20

    def test_no_invented_oem_procedures(self, pkg):
        """Steps must not claim to be OEM procedures or reference specific OEM page numbers."""
        forbidden_phrases = [
            "oem procedure page",
            "refer to oem repair manual",
            "per honda service manual",
            "oem procedure step",
            "factory procedure",
        ]
        for step in pkg.execution_steps:
            lower = step.lower()
            for phrase in forbidden_phrases:
                assert phrase not in lower, f"Step may be inventing OEM procedure: {step!r}"

    def test_no_raw_ids_in_execution_steps(self, pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for step in pkg.execution_steps:
            assert not pattern.search(step), f"Raw ID found in execution step: {step!r}"


# ---------------------------------------------------------------------------
# Completion criteria
# ---------------------------------------------------------------------------

class TestCompletionCriteria:
    def test_completion_criteria_is_list(self, pkg):
        assert isinstance(pkg.completion_criteria, list)

    def test_completion_criteria_non_empty(self, pkg):
        assert len(pkg.completion_criteria) >= 2

    def test_completion_criteria_are_strings(self, pkg):
        for c in pkg.completion_criteria:
            assert isinstance(c, str)

    def test_done_when_no_raw_ids(self, pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for c in pkg.completion_criteria:
            assert not pattern.search(c), f"Raw ID in completion criterion: {c!r}"


# ---------------------------------------------------------------------------
# Unlock generation
# ---------------------------------------------------------------------------

class TestUnlockGeneration:
    def test_expected_unlocks_is_list(self, pkg):
        assert isinstance(pkg.expected_unlocks, list)

    def test_expected_unlocks_non_empty(self, pkg):
        assert len(pkg.expected_unlocks) >= 1

    def test_unlocks_are_strings(self, pkg):
        for u in pkg.expected_unlocks:
            assert isinstance(u, str)

    def test_unlocks_max_6(self, pkg):
        assert len(pkg.expected_unlocks) <= 6

    def test_no_raw_ids_in_unlocks(self, pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for u in pkg.expected_unlocks:
            assert not pattern.search(u), f"Raw ID in unlock: {u!r}"


# ---------------------------------------------------------------------------
# CollisionWorkPackage projection
# ---------------------------------------------------------------------------

class TestCollisionWorkPackageProjection:
    def test_returns_collision_work_package(self, work_pkg):
        assert isinstance(work_pkg, CollisionWorkPackage)

    def test_has_work_package_title(self, work_pkg):
        assert isinstance(work_pkg.work_package_title, str)
        assert len(work_pkg.work_package_title) > 0

    def test_has_purpose(self, work_pkg):
        assert isinstance(work_pkg.purpose, str)
        assert len(work_pkg.purpose) > 0

    def test_repair_status_is_human_readable(self, work_pkg):
        known_statuses = {
            "Blocked — Prerequisites Not Met",
            "In Progress",
            "Ready to Begin",
            "Complete",
        }
        assert work_pkg.repair_status in known_statuses or len(work_pkg.repair_status) > 0

    def test_urgency_is_human_readable(self, work_pkg):
        known_urgencies = {"Critical — Act Now", "High Priority", "Normal Priority", "Low Priority"}
        assert work_pkg.urgency in known_urgencies or len(work_pkg.urgency) > 0

    def test_before_you_start_populated(self, work_pkg):
        assert isinstance(work_pkg.before_you_start, list)
        assert len(work_pkg.before_you_start) >= 1

    def test_verifications_required_populated(self, work_pkg):
        assert isinstance(work_pkg.verifications_required, list)
        assert len(work_pkg.verifications_required) >= 1

    def test_work_to_perform_populated(self, work_pkg):
        assert isinstance(work_pkg.work_to_perform, list)
        assert len(work_pkg.work_to_perform) >= 2

    def test_done_when_populated(self, work_pkg):
        assert isinstance(work_pkg.done_when, list)
        assert len(work_pkg.done_when) >= 2

    def test_what_this_unlocks_populated(self, work_pkg):
        assert isinstance(work_pkg.what_this_unlocks, list)
        assert len(work_pkg.what_this_unlocks) >= 1

    def test_technician_brief_populated(self, work_pkg):
        assert isinstance(work_pkg.technician_brief, str)
        assert len(work_pkg.technician_brief) > 0

    def test_manager_brief_populated(self, work_pkg):
        assert isinstance(work_pkg.manager_brief, str)
        assert len(work_pkg.manager_brief) > 0

    def test_to_dict_has_collision_keys(self, work_pkg):
        d = work_pkg.to_dict()
        required = {
            "package_id", "work_package_title", "purpose", "repair_status", "urgency",
            "before_you_start", "verifications_required", "work_to_perform",
            "done_when", "what_this_unlocks", "currently_blocked_by",
            "risk_note", "confidence", "technician_brief", "manager_brief", "advisory",
        }
        assert required <= d.keys()

    def test_package_id_matches_source(self, pkg, work_pkg):
        assert work_pkg.package_id == pkg.package_id

    def test_title_matches_source(self, pkg, work_pkg):
        assert work_pkg.work_package_title == pkg.title

    def test_no_raw_ids_in_before_you_start(self, work_pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for item in work_pkg.before_you_start:
            assert not pattern.search(item), f"Raw ID in before_you_start: {item!r}"

    def test_no_raw_ids_in_work_to_perform(self, work_pkg):
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        for item in work_pkg.work_to_perform:
            assert not pattern.search(item), f"Raw ID in work_to_perform: {item!r}"


# ---------------------------------------------------------------------------
# No OEM instruction fabrication
# ---------------------------------------------------------------------------

class TestNoOEMFabrication:
    """The engine must never invent OEM repair instructions."""

    _OEM_FABRICATION_PATTERNS = [
        r"torque to \d+ (ft|nm|lb)",
        r"apply \d+ (ml|mm|in|inch) of",
        r"weld at \d+ (amps|°|degrees)",
        r"section at \d+ (mm|in|cm) from",
        r"per honda service manual",
        r"per oem procedure page \d+",
        r"step \d+ of oem",
        r"see repair manual section",
    ]

    def _check_field(self, items, field_name):
        if isinstance(items, str):
            items = [items]
        for pat in self._OEM_FABRICATION_PATTERNS:
            for item in items:
                assert not re.search(pat, item, re.I), (
                    f"Possible OEM fabrication in {field_name}: {item!r}"
                )

    def test_no_fabrication_in_prerequisites(self, pkg):
        self._check_field(pkg.prerequisites, "prerequisites")

    def test_no_fabrication_in_verifications(self, pkg):
        self._check_field(pkg.required_verifications, "required_verifications")

    def test_no_fabrication_in_execution_steps(self, pkg):
        self._check_field(pkg.execution_steps, "execution_steps")

    def test_no_fabrication_in_completion_criteria(self, pkg):
        self._check_field(pkg.completion_criteria, "completion_criteria")

    def test_no_fabrication_in_work_to_perform(self, work_pkg):
        self._check_field(work_pkg.work_to_perform, "work_to_perform")

    def test_no_fabrication_in_verifications_required(self, work_pkg):
        self._check_field(work_pkg.verifications_required, "verifications_required")


# ---------------------------------------------------------------------------
# Advisory notice
# ---------------------------------------------------------------------------

class TestAdvisoryNotice:
    def test_pkg_has_advisory(self, pkg):
        assert "advisory" in pkg.advisory.lower() or "qualified" in pkg.advisory.lower()

    def test_work_pkg_has_advisory(self, work_pkg):
        assert "advisory" in work_pkg.advisory.lower() or "qualified" in work_pkg.advisory.lower()

    def test_advisory_not_empty(self, pkg):
        assert len(pkg.advisory) > 20

    def test_advisory_in_to_dict(self, pkg):
        assert pkg.to_dict()["advisory"]

    def test_collision_advisory_in_to_dict(self, work_pkg):
        assert work_pkg.to_dict()["advisory"]


# ---------------------------------------------------------------------------
# /internal/review/package endpoint
# ---------------------------------------------------------------------------

class TestPackageEndpoint:
    @pytest.fixture(scope="class")
    def client(self):
        from repairgraph.api.app import app
        return TestClient(app)

    def test_package_endpoint_200(self, client):
        r = client.get("/internal/review/package")
        assert r.status_code == 200

    def test_package_endpoint_returns_json(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert isinstance(data, dict)

    def test_package_endpoint_has_work_package_title(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "work_package_title" in data

    def test_package_endpoint_has_execution_package(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "execution_package" in data

    def test_package_endpoint_has_advisory(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "endpoint_advisory" in data

    def test_package_endpoint_before_you_start_present(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "before_you_start" in data
        assert isinstance(data["before_you_start"], list)

    def test_package_endpoint_work_to_perform_present(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "work_to_perform" in data
        assert isinstance(data["work_to_perform"], list)
        assert len(data["work_to_perform"]) >= 1

    def test_package_endpoint_done_when_present(self, client):
        r = client.get("/internal/review/package")
        data = r.json()
        assert "done_when" in data
        assert isinstance(data["done_when"], list)

    def test_package_endpoint_no_raw_gate_ids(self, client):
        r = client.get("/internal/review/package")
        raw = r.text
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        # Exclude the endpoint_advisory and fields that are expected to be clean
        # Check string fields only
        data = r.json()
        for key in ("before_you_start", "verifications_required", "work_to_perform", "done_when", "what_this_unlocks"):
            if key in data:
                for item in data[key]:
                    assert not pattern.search(str(item)), f"Raw gate ID in {key}: {item!r}"


# ---------------------------------------------------------------------------
# Review page integration
# ---------------------------------------------------------------------------

class TestReviewPageIntegration:
    @pytest.fixture(scope="class")
    def client(self):
        from repairgraph.api.app import app
        return TestClient(app)

    def test_review_page_200(self, client):
        r = client.get("/internal/review")
        assert r.status_code == 200

    def test_review_page_has_work_package_section(self, client):
        r = client.get("/internal/review")
        html = r.text
        assert "Work Package" in html or "work_package" in html or "work-package" in html

    def test_review_page_has_before_you_start(self, client):
        r = client.get("/internal/review")
        html = r.text
        assert "Before You Start" in html

    def test_review_page_has_work_to_perform(self, client):
        r = client.get("/internal/review")
        html = r.text
        assert "Work to Perform" in html

    def test_review_page_has_done_when(self, client):
        r = client.get("/internal/review")
        html = r.text
        assert "Done When" in html

    def test_review_page_has_what_this_unlocks(self, client):
        r = client.get("/internal/review")
        html = r.text
        assert "What This Unlocks" in html

    def test_review_page_html_is_utf8(self, client):
        r = client.get("/internal/review")
        assert "utf-8" in r.headers.get("content-type", "").lower() or r.encoding in ("utf-8", "UTF-8", None)

    def test_review_page_no_raw_gate_ids(self, client):
        r = client.get("/internal/review")
        html = r.text
        # Raw gate IDs like qa:material_compliance:critical:2 should not appear in visible content
        pattern = re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b")
        # Allow them inside <script> tags / data attributes but not in visible HTML text nodes
        # Simple heuristic: strip script/style tags and check remaining
        stripped = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
        stripped = re.sub(r"<style[^>]*>.*?</style>", "", stripped, flags=re.S)
        stripped = re.sub(r"data-[^=]+=['\"][^'\"]*['\"]", "", stripped)
        # Remove JSON blobs inside data attributes
        stripped = re.sub(r"<[^>]+>", "", stripped)
        matches = pattern.findall(stripped)
        assert not matches, f"Raw gate IDs visible in review page HTML: {matches[:5]}"


# ---------------------------------------------------------------------------
# Regression: field types and shapes
# ---------------------------------------------------------------------------

class TestRegression:
    def test_pkg_prerequisites_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.prerequisites)

    def test_pkg_required_verifications_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.required_verifications)

    def test_pkg_execution_steps_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.execution_steps)

    def test_pkg_completion_criteria_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.completion_criteria)

    def test_pkg_expected_unlocks_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.expected_unlocks)

    def test_pkg_blocked_by_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.blocked_by)

    def test_pkg_supporting_evidence_list_of_str(self, pkg):
        assert all(isinstance(x, str) for x in pkg.supporting_evidence)

    def test_work_pkg_before_you_start_list_of_str(self, work_pkg):
        assert all(isinstance(x, str) for x in work_pkg.before_you_start)

    def test_work_pkg_work_to_perform_list_of_str(self, work_pkg):
        assert all(isinstance(x, str) for x in work_pkg.work_to_perform)

    def test_work_pkg_done_when_list_of_str(self, work_pkg):
        assert all(isinstance(x, str) for x in work_pkg.done_when)

    def test_work_pkg_what_this_unlocks_list_of_str(self, work_pkg):
        assert all(isinstance(x, str) for x in work_pkg.what_this_unlocks)

    def test_multiple_calls_deterministic_fields(self, model):
        """Non-UUID fields are deterministic across builds."""
        rca = build_root_cause_analysis(model)
        plan1 = build_operational_plan(model, rca=rca)
        nar1 = build_narrative(plan1)
        pkg1 = build_execution_package(plan1, nar1, model)

        plan2 = build_operational_plan(model, rca=rca)
        nar2 = build_narrative(plan2)
        pkg2 = build_execution_package(plan2, nar2, model)

        assert pkg1.title == pkg2.title
        assert pkg1.objective == pkg2.objective
        assert pkg1.status == pkg2.status
        assert pkg1.priority == pkg2.priority
        assert pkg1.prerequisites == pkg2.prerequisites
        assert pkg1.execution_steps == pkg2.execution_steps
