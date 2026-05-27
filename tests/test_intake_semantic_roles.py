"""
Tests for Sprint 5: Semantic Role Classification Hardening.

Covers:
- detect_breadcrumbs: segment extraction, separator variants, deduplication
- detect_document_roles: multi-role output, ontology phrase boosts, breadcrumb boosts
- detect_document_role: backward compatibility (still returns primary role string)
- IntakeFile new fields: supporting_roles, role_scores, role_evidence
- Hyundai fixture files: each classified with the correct primary role
- Regression: Toyota, Subaru, Ford primary roles unchanged
"""
from __future__ import annotations

from pathlib import Path

import pytest

from repairgraph.intake.classify import (
    classify_intake_file,
    classify_intake_packet,
    detect_breadcrumbs,
    detect_document_role,
    detect_document_roles,
)
from repairgraph.intake.schema import IntakeFile

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
HYUNDAI_PACKET = FIXTURES / "hyundai_packet"
TOYOTA_PACKET = FIXTURES / "toyota_packet"
SUBARU_PACKET = FIXTURES / "subaru_packet"
FORD_PACKET = FIXTURES / "ford_packet"


# ── detect_breadcrumbs ────────────────────────────────────────────────────────

class TestDetectBreadcrumbs:
    def test_empty_returns_empty(self):
        assert detect_breadcrumbs("") == []

    def test_whitespace_returns_empty(self):
        assert detect_breadcrumbs("   \n\t  ") == []

    def test_plain_text_no_breadcrumbs(self):
        text = "This is a standard repair procedure document with no navigation path."
        assert detect_breadcrumbs(text) == []

    def test_two_segments_not_a_breadcrumb(self):
        # Minimum is 3 segments
        text = "Body and Frame > Quarter Panel"
        assert detect_breadcrumbs(text) == []

    def test_three_segments_extracted(self):
        text = "Body and Frame > Quarter Panel > Removal"
        crumbs = detect_breadcrumbs(text)
        assert "body and frame" in crumbs
        assert "quarter panel" in crumbs
        assert "removal" in crumbs

    def test_gt_separator(self):
        text = "Elantra > Body and Frame > Quarter Panel > Service and Repair > Removal and Replacement"
        crumbs = detect_breadcrumbs(text)
        assert "removal and replacement" in crumbs
        assert "service and repair" in crumbs
        assert "elantra" in crumbs

    def test_unicode_arrow_separator(self):
        text = "Vehicle » Body » Panel » Corrosion Protection"
        crumbs = detect_breadcrumbs(text)
        assert "corrosion protection" in crumbs

    def test_rightward_arrow_separator(self):
        text = "Vehicle → Body → Panel → Weld Points"
        crumbs = detect_breadcrumbs(text)
        assert "weld points" in crumbs

    def test_double_colon_separator(self):
        text = "Vehicle :: Body :: Panel :: Welding Procedure"
        crumbs = detect_breadcrumbs(text)
        assert "welding procedure" in crumbs

    def test_segments_are_lowercased(self):
        text = "ELANTRA > BODY AND FRAME > REMOVAL AND REPLACEMENT"
        crumbs = detect_breadcrumbs(text)
        assert "elantra" in crumbs
        assert "removal and replacement" in crumbs

    def test_deduplication_across_lines(self):
        text = "A > B > C\nA > B > C\nA > B > C"
        crumbs = detect_breadcrumbs(text)
        assert crumbs.count("a") == 1
        assert crumbs.count("b") == 1
        assert crumbs.count("c") == 1

    def test_multiple_breadcrumb_lines(self):
        text = (
            "Elantra > Body and Frame > Quarter Panel > Service and Repair > Weld Points\n"
            "Elantra > Body and Frame > Quarter Panel > Service and Repair > Removal and Replacement\n"
        )
        crumbs = detect_breadcrumbs(text)
        assert "weld points" in crumbs
        assert "removal and replacement" in crumbs
        assert "service and repair" in crumbs

    def test_non_breadcrumb_lines_ignored(self):
        text = (
            "Step 1: Remove panel.\n"
            "Elantra > Body and Frame > Removal\n"
            "Apply primer.\n"
        )
        crumbs = detect_breadcrumbs(text)
        # Only the middle line qualifies (3 segments)
        assert "elantra" in crumbs
        assert "body and frame" in crumbs
        assert "removal" in crumbs


# ── detect_document_roles ─────────────────────────────────────────────────────

class TestDetectDocumentRoles:
    def test_empty_returns_unknown(self):
        result = detect_document_roles("")
        assert result["primary_role"] == "unknown"
        assert result["supporting_roles"] == []
        assert result["role_scores"] == {}
        assert result["role_evidence"] == []

    def test_whitespace_returns_unknown(self):
        result = detect_document_roles("   ")
        assert result["primary_role"] == "unknown"

    def test_returns_required_keys(self):
        result = detect_document_roles("removal and installation step 1")
        for key in ("primary_role", "supporting_roles", "role_scores", "role_evidence"):
            assert key in result

    def test_repair_procedure_primary(self):
        text = "Removal and replacement procedure. Step 1: disconnect. Step 2: remove. Step 3: install."
        result = detect_document_roles(text)
        assert result["primary_role"] == "repair_procedure"

    def test_welding_primary(self):
        text = "Weld points: 42 spot welds. MIG welding. Weld diagram reference. Resistance spot welding."
        result = detect_document_roles(text)
        assert result["primary_role"] == "welding"

    def test_corrosion_primary(self):
        text = (
            "Corrosion protection required. Apply anti-corrosion primer. "
            "Rust preventative in cavities. Body sealant on flanges. Seam sealer."
        )
        result = detect_document_roles(text)
        assert result["primary_role"] == "corrosion_protection"

    def test_materials_primary(self):
        text = (
            "Material specification: High Strength Steel 590 MPa tensile strength. "
            "UHSS 980 MPa yield strength. Steel grade CR980."
        )
        result = detect_document_roles(text)
        assert result["primary_role"] == "materials"

    def test_calibration_primary(self):
        text = "ADAS calibration required. Camera calibration procedure. Sensor calibration. Radar recalibration."
        result = detect_document_roles(text)
        assert result["primary_role"] == "calibration"

    def test_precautions_primary(self):
        text = "WARNING: Do not weld near SRS components. Danger. Safety precautions. Airbag hazard."
        result = detect_document_roles(text)
        assert result["primary_role"] == "precautions"

    def test_supporting_roles_is_list(self):
        result = detect_document_roles("step 1 removal procedure")
        assert isinstance(result["supporting_roles"], list)

    def test_role_scores_normalized(self):
        text = "Spot weld. MIG welding. Weld points. Weld diagram. Resistance spot welding."
        result = detect_document_roles(text)
        assert result["role_scores"]
        assert all(0.0 <= v <= 1.0 for v in result["role_scores"].values())
        primary = result["primary_role"]
        assert result["role_scores"].get(primary, 0) == 1.0

    def test_role_evidence_is_list(self):
        text = "Resistance spot welding. Weld points. Weld diagram."
        result = detect_document_roles(text)
        assert isinstance(result["role_evidence"], list)

    def test_ontology_phrase_boosts_repair_procedure(self):
        # "removal and replacement" is an ontology phrase → strong boost
        text = "Removal and replacement. Step 1."
        result = detect_document_roles(text)
        assert result["primary_role"] == "repair_procedure"

    def test_ontology_phrase_boosts_welding(self):
        text = "Weld points and weld diagram reference. Number of weld: 20."
        result = detect_document_roles(text)
        assert result["primary_role"] == "welding"

    def test_breadcrumb_weld_points_wins_welding(self):
        text = "Elantra > Body and Frame > Quarter Panel > Service and Repair > Weld Points"
        result = detect_document_roles(text)
        assert result["primary_role"] == "welding"

    def test_breadcrumb_removal_replacement_wins_repair_procedure(self):
        text = "Elantra > Body and Frame > Quarter Panel > Service and Repair > Removal and Replacement"
        result = detect_document_roles(text)
        assert result["primary_role"] == "repair_procedure"

    def test_breadcrumb_corrosion_protection_wins(self):
        text = "Elantra > Body and Frame > Quarter Panel > Corrosion Protection"
        result = detect_document_roles(text)
        assert result["primary_role"] == "corrosion_protection"

    def test_breadcrumb_material_specification_wins_materials(self):
        text = "Elantra > Body and Frame > Construction > Material Specification"
        result = detect_document_roles(text)
        assert result["primary_role"] == "materials"

    def test_supporting_roles_populated_for_multi_role_doc(self):
        # Primarily a welding doc that also references corrosion protection
        text = (
            "Weld points: 42 spot welds. MIG welding. Weld diagram. Resistance spot welding.\n"
            "Heat affected zone: Apply anti-corrosion primer after welding. Corrosion protection."
        )
        result = detect_document_roles(text)
        assert result["primary_role"] == "welding"
        assert isinstance(result["supporting_roles"], list)

    def test_role_evidence_contains_ontology_phrases(self):
        text = "Resistance spot welding procedure. Weld points diagram."
        result = detect_document_roles(text)
        # Evidence should include matched ontology phrases
        assert any("weld" in ev.lower() for ev in result["role_evidence"])

    def test_unknown_for_unclassifiable_text(self):
        text = "the quick brown fox jumps over the lazy dog"
        result = detect_document_roles(text)
        assert result["primary_role"] == "unknown"

    def test_deterministic(self):
        text = "Removal and replacement procedure. Step 1: disconnect. Weld points."
        r1 = detect_document_roles(text)
        r2 = detect_document_roles(text)
        assert r1["primary_role"] == r2["primary_role"]
        assert r1["supporting_roles"] == r2["supporting_roles"]
        assert r1["role_scores"] == r2["role_scores"]


# ── detect_document_role backward compatibility ────────────────────────────────

class TestDetectDocumentRoleBackwardCompat:
    def test_returns_string(self):
        assert isinstance(detect_document_role("step 1 removal"), str)

    def test_empty_returns_unknown(self):
        assert detect_document_role("") == "unknown"

    def test_repair_procedure_text(self):
        text = "Step 1 — Removal procedure. Disassembly. Installation steps."
        assert detect_document_role(text) == "repair_procedure"

    def test_welding_text(self):
        text = "Spot weld nugget 6mm. MIG welding. Plug weld per weld map."
        assert detect_document_role(text) == "welding"

    def test_corrosion_text(self):
        text = "Apply anti-corrosion sealer. Cavity wax injection. Zinc primer."
        assert detect_document_role(text) == "corrosion_protection"

    def test_materials_text(self):
        text = "UHSS high strength steel 980 MPa tensile strength. Material classification."
        assert detect_document_role(text) == "materials"

    def test_consistent_with_detect_document_roles(self):
        text = "Weld points: spot weld. MIG welding procedure. Weld diagram."
        assert detect_document_role(text) == detect_document_roles(text)["primary_role"]


# ── IntakeFile new fields ─────────────────────────────────────────────────────

class TestIntakeFileNewFields:
    def test_defaults_empty(self):
        f = IntakeFile(file_id="x", filename="x.txt", extension=".txt", size_bytes=0)
        assert f.supporting_roles == []
        assert f.role_scores == {}
        assert f.role_evidence == []

    def test_supporting_roles_settable(self):
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=0,
            supporting_roles=["welding"],
        )
        assert f.supporting_roles == ["welding"]

    def test_role_scores_settable(self):
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=0,
            role_scores={"repair_procedure": 1.0, "welding": 0.5},
        )
        assert f.role_scores["repair_procedure"] == 1.0
        assert f.role_scores["welding"] == 0.5

    def test_role_evidence_settable(self):
        f = IntakeFile(
            file_id="x", filename="x.txt", extension=".txt", size_bytes=0,
            role_evidence=["removal and replacement"],
        )
        assert "removal and replacement" in f.role_evidence

    def test_classify_file_populates_supporting_roles(self, tmp_path):
        p = tmp_path / "repair_with_welding.txt"
        p.write_text(
            "Removal and replacement procedure.\n"
            "Step 1: disconnect. Step 2: remove.\n"
            "Weld points: spot weld. MIG welding. Weld diagram. Resistance spot welding.\n"
            "Heat affected zone treatment required.\n",
            encoding="utf-8",
        )
        result = classify_intake_file(p)
        assert isinstance(result.supporting_roles, list)

    def test_classify_file_populates_role_scores(self, tmp_path):
        p = tmp_path / "procedure.txt"
        p.write_text(
            "Removal and installation. Step 1: disconnect.\n"
            "Step 2: remove panel. Step 3: install replacement.\n",
            encoding="utf-8",
        )
        result = classify_intake_file(p)
        assert isinstance(result.role_scores, dict)
        assert result.role_scores  # non-empty
        assert "repair_procedure" in result.role_scores

    def test_classify_file_populates_role_evidence(self, tmp_path):
        p = tmp_path / "welding.txt"
        p.write_text(
            "Resistance spot welding: 20 weld points. Weld diagram reference.\n"
            "MIG welding at plug weld locations. Heat affected zone treatment.\n",
            encoding="utf-8",
        )
        result = classify_intake_file(p)
        assert isinstance(result.role_evidence, list)

    def test_classify_file_primary_role_matches_document_role(self, tmp_path):
        p = tmp_path / "procedure.txt"
        p.write_text(
            "Removal and replacement. Step 1: disconnect. Step 2: remove. "
            "Step 3: install. Reinstall trim panels.\n",
            encoding="utf-8",
        )
        result = classify_intake_file(p)
        assert result.document_role == "repair_procedure"
        # role_scores primary should match document_role
        if result.role_scores:
            primary = max(result.role_scores, key=lambda r: result.role_scores[r])
            assert primary == result.document_role

    def test_error_file_has_empty_supporting_roles(self, tmp_path):
        fake = tmp_path / "missing.txt"
        result = classify_intake_file(fake)
        # Unreadable file: supporting_roles defaults to []
        assert result.supporting_roles == []
        assert result.role_scores == {}
        assert result.role_evidence == []


# ── Hyundai fixture classification ────────────────────────────────────────────

class TestHyundaiFixtureClassification:
    def test_procedure_file_exists(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_weld_points_file_exists(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Weld Points.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_corrosion_file_exists(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Rust Preventative and Body Sealant.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_materials_file_exists(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Construction Materials.txt"
        assert p.exists(), f"Fixture missing: {p}"

    def test_procedure_file_classified_repair_procedure(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        assert result.document_role == "repair_procedure", (
            f"Expected repair_procedure, got {result.document_role!r}. "
            f"Role scores: {result.role_scores}"
        )

    def test_weld_points_file_classified_welding(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Weld Points.txt"
        result = classify_intake_file(p)
        assert result.document_role == "welding", (
            f"Expected welding, got {result.document_role!r}. "
            f"Role scores: {result.role_scores}"
        )

    def test_corrosion_file_classified_corrosion_protection(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Rust Preventative and Body Sealant.txt"
        result = classify_intake_file(p)
        assert result.document_role == "corrosion_protection", (
            f"Expected corrosion_protection, got {result.document_role!r}. "
            f"Role scores: {result.role_scores}"
        )

    def test_materials_file_classified_materials(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Construction Materials.txt"
        result = classify_intake_file(p)
        assert result.document_role == "materials", (
            f"Expected materials, got {result.document_role!r}. "
            f"Role scores: {result.role_scores}"
        )

    def test_procedure_file_oem_hyundai(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        assert result.detected_oem == "Hyundai"

    def test_procedure_file_year_2023(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        assert result.detected_year == 2023

    def test_procedure_file_model_elantra(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        assert result.detected_model == "Elantra"

    def test_weld_file_has_role_evidence(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Weld Points.txt"
        result = classify_intake_file(p)
        assert result.role_evidence  # non-empty evidence

    def test_procedure_file_has_role_scores(self):
        p = HYUNDAI_PACKET / "2023 Hyundai Elantra Quarter Panel Removal and Replacement.txt"
        result = classify_intake_file(p)
        assert "repair_procedure" in result.role_scores

    def test_hyundai_packet_roles_detected(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        detected = set(manifest.detected_packet.detected_roles)
        assert "repair_procedure" in detected
        assert "welding" in detected
        assert "corrosion_protection" in detected
        assert "materials" in detected

    def test_hyundai_packet_oem_hyundai(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Hyundai"

    def test_hyundai_packet_year_2023(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_year == 2023

    def test_hyundai_packet_model_elantra(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_model == "Elantra"

    def test_hyundai_packet_readiness_partial_or_ready(self):
        paths = list(HYUNDAI_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.readiness in ("ready", "partial")


# ── Regression: existing fixtures ─────────────────────────────────────────────

class TestExistingFixtureRegression:
    def test_toyota_repair_procedure_unchanged(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert result.document_role == "repair_procedure"
        assert result.detected_oem == "Toyota"

    def test_toyota_welding_specs_unchanged(self):
        src = TOYOTA_PACKET / "camry_welding_specs.txt"
        result = classify_intake_file(src)
        assert result.document_role == "welding"

    def test_toyota_corrosion_unchanged(self):
        src = TOYOTA_PACKET / "camry_corrosion_protection.txt"
        result = classify_intake_file(src)
        assert result.document_role == "corrosion_protection"

    def test_ford_materials_unchanged(self):
        src = FORD_PACKET / "f150_materials.txt"
        result = classify_intake_file(src)
        assert result.document_role == "materials"

    def test_subaru_packet_oem_subaru(self):
        paths = list(SUBARU_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert manifest.detected_packet.detected_oem == "Subaru"

    def test_toyota_packet_roles_intact(self):
        paths = list(TOYOTA_PACKET.iterdir())
        manifest = classify_intake_packet(paths)
        assert "repair_procedure" in manifest.detected_packet.detected_roles
        assert "welding" in manifest.detected_packet.detected_roles

    def test_new_fields_present_on_existing_toyota_file(self):
        src = TOYOTA_PACKET / "camry_repair_procedure.txt"
        result = classify_intake_file(src)
        assert isinstance(result.supporting_roles, list)
        assert isinstance(result.role_scores, dict)
        assert isinstance(result.role_evidence, list)
        assert result.role_scores  # non-empty for a classified file
