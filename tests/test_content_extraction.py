"""Tests for deterministic content extraction: document text → structured
procedure facts → normalized procedure → compilable OperationalModel.

The extractor is rule-based (no OCR/ML/LLMs) and must never fabricate:
facts exist only when the document text pattern-matches, and every fact
carries the source snippet it was derived from.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from repairgraph.intake.content_extractor import (
    _components_in,
    extract_document_facts,
)

RICH_DOC = """2022 Nissan Altima Quarter Panel Replacement

Before removal, inspect the rear pillar gutter for damage. Check the wheel arch
separator for deformation.

Replace the rear quarter outer panel and the wheel arch separator.

The rear quarter outer panel is adjacent to the quarter pillar stiffener.
The wheel arch separator is welded to the rear quarter outer panel.

Sectioning: make the cut along the front upper edge of the quarter panel,
30 mm from the pillar seam.

Joining: 8 spot welds along the upper flange. 4 plug welds. MIG brazing
required adjacent to the roof rail. Apply adhesive bonding along the wheel arch.

The quarter pillar stiffener is 1470 MPa hot-stamped steel. Warning: do not
apply heat to components above 980 MPa.

Apply seam sealer to all joints. Cavity wax must be applied inside the sill.
"""


@pytest.fixture
def facts():
    return extract_document_facts(RICH_DOC)


# ---------------------------------------------------------------------------
# Component recognition
# ---------------------------------------------------------------------------

class TestComponentRecognition:
    def test_finds_multiword_components(self, facts):
        assert "rear_quarter_outer_panel" in facts["components"]
        assert "wheel_arch_separator" in facts["components"]
        assert "quarter_pillar_stiffener" in facts["components"]

    def test_verb_prefixed_phrase_recovers_component(self):
        # Greedy match absorbs 'inspect the rear pillar'; the scanner must
        # re-enter the span and find the real component.
        assert _components_in(
            "Before removal, inspect the rear pillar gutter for damage."
        ) == ["rear_pillar_gutter"]

    def test_bare_structural_noun_rejected(self):
        assert _components_in("Remove the panel.") == []

    def test_junk_words_rejected(self):
        comps = _components_in("Measure 30 mm from the pillar seam.")
        assert all("mm" not in c and "from" not in c for c in comps)

    def test_line_wrapped_component_survives(self):
        # PDF extraction hard-wraps lines mid-phrase
        text = "Check the wheel arch\nseparator for deformation."
        facts = extract_document_facts(text)
        assert "wheel_arch_separator" in facts["components"]


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

class TestDependencies:
    def test_replace_dependency(self, facts):
        deps = {(d["type"], d["target"]) for d in facts["dependencies"]}
        assert ("replace_component", "rear_quarter_outer_panel") in deps
        assert ("replace_component", "wheel_arch_separator") in deps

    def test_inspect_dependency(self, facts):
        deps = {(d["type"], d["target"]) for d in facts["dependencies"]}
        assert ("inspect_if_damaged", "rear_pillar_gutter") in deps


class TestSpatialRelationships:
    def test_adjacent_to(self, facts):
        rels = {(r["source"], r["relationship"], r["target"]) for r in facts["spatial_relationships"]}
        assert ("rear_quarter_outer_panel", "adjacent_to", "quarter_pillar_stiffener") in rels

    def test_welded_to_maps_to_joined_to(self, facts):
        rels = {(r["source"], r["relationship"], r["target"]) for r in facts["spatial_relationships"]}
        assert ("wheel_arch_separator", "joined_to", "rear_quarter_outer_panel") in rels

    def test_relationships_use_allowed_types(self, facts):
        from repairgraph.topology.schema import ALLOWED_SPATIAL_RELATIONSHIPS
        for r in facts["spatial_relationships"]:
            assert r["relationship"] in ALLOWED_SPATIAL_RELATIONSHIPS


class TestSectioning:
    def test_sectioning_zone_and_dimension(self, facts):
        zones = {s["zone"]: s for s in facts["sectioning_locations"]}
        assert "quarter_panel" in zones
        assert zones["quarter_panel"]["dimension_mm"] == 30.0


class TestJoiningMethods:
    def test_methods_with_counts(self, facts):
        methods = {j["method"]: j for j in facts["joining_methods"]}
        assert methods["spot_weld"]["count"] == 8
        assert methods["plug_weld"]["count"] == 4
        assert "mig_brazing" in methods
        assert "adhesive_bonding" in methods

    def test_mig_brazing_does_not_double_as_generic_brazing(self, facts):
        methods = {j["method"] for j in facts["joining_methods"]}
        assert "brazing" not in methods


class TestMaterials:
    def test_uhss_classification(self, facts):
        mats = {m["component"]: m for m in facts["materials"]}
        stiffener = mats["quarter_pillar_stiffener"]
        assert stiffener["tensile_strength_mpa"] == 1470
        assert stiffener["classification"] == "UHSS"

    def test_hss_and_mild_thresholds(self):
        f = extract_document_facts(
            "The rear roof rail is 590 MPa steel. The outer wheel arch separator is 270 MPa."
        )
        mats = {m["component"]: m["classification"] for m in f["materials"]}
        assert mats["rear_roof_rail"] == "HSS"
        assert mats["outer_wheel_arch_separator"] == "mild_steel"

    def test_thickness_and_zinc(self):
        f = extract_document_facts(
            "Roof side rail stiffener thickness 0.65 mm sheet, zinc-coated."
        )
        m = f["materials"][0]
        assert m["thickness_mm"] == 0.65
        assert m["zinc_plated"] is True


class TestCorrosionAndNotes:
    def test_corrosion_requirements(self, facts):
        reqs = {r["requirement"] for r in facts["corrosion_requirements"]}
        assert "sealer_application_required" in reqs
        assert "undercoating_application_required" in reqs

    def test_repair_notes_capture_warnings(self, facts):
        assert any("do not" in n.lower() for n in facts["repair_notes"])


# ---------------------------------------------------------------------------
# Trust semantics: never fabricate, always evidence
# ---------------------------------------------------------------------------

class TestTrustSemantics:
    def test_empty_text_extracts_nothing(self):
        facts = extract_document_facts("")
        assert all(v == [] for v in facts.values())

    def test_unstated_facts_stay_empty(self):
        facts = extract_document_facts("Apply seam sealer to all joints.")
        assert facts["dependencies"] == []
        assert facts["spatial_relationships"] == []
        assert facts["sectioning_locations"] == []
        assert facts["materials"] == []

    def test_every_fact_carries_source_snippet(self, facts):
        for key in ("dependencies", "spatial_relationships", "sectioning_locations",
                    "joining_methods", "corrosion_requirements", "materials"):
            for item in facts[key]:
                ev = item["evidence"]
                assert ev["source_type"] == "document_text"
                assert ev["requires_oem_verification"] is True
                assert ev["basis"] and ev["basis"][0].strip()

    def test_facts_are_json_serializable(self, facts):
        import json
        json.dumps(facts)


# ---------------------------------------------------------------------------
# Pipeline integration: classify → normalize → compile
# ---------------------------------------------------------------------------

def _classify_doc(tmp: Path, name: str = "2022_nissan_altima_quarter_panel_replacement.txt"):
    from repairgraph.intake.classify import classify_intake_packet
    doc = tmp / name
    doc.write_text(RICH_DOC, encoding="utf-8")
    return classify_intake_packet([doc])


class TestClassifyCarriesFacts:
    def test_intake_file_has_extracted_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _classify_doc(Path(tmp))
        facts = manifest.files[0].extracted_facts
        assert facts is not None
        assert "rear_quarter_outer_panel" in facts["components"]


class TestNormalizerMergesFacts:
    def _normalized(self, tmp: Path):
        from repairgraph.intake.normalizer import normalize_intake_manifest
        manifest = _classify_doc(tmp)
        return normalize_intake_manifest(manifest, output_dir=tmp / "normalized")

    def test_procedure_has_extracted_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._normalized(Path(tmp))
        proc = result.procedure
        assert proc["dependencies"], "dependencies must come from document text"
        assert proc["spatial_relationships"]
        assert proc["repair_notes"]
        assert any(s.get("dimension_mm") == 30.0 for s in proc["sectioning_locations"])
        assert "spot_weld" in proc["joining_methods"]

    def test_structure_has_materials_and_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._normalized(Path(tmp))
        struct = result.structure
        assert any(m["component"] == "quarter_pillar_stiffener" for m in struct["materials"])
        assert "rear_quarter_outer_panel" in struct["structure_nodes"]

    def test_vehicle_title_noise_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._normalized(Path(tmp))
        for node in result.structure["structure_nodes"]:
            assert "altima" not in node
            assert "nissan" not in node


class TestEndToEndCompilation:
    def test_uploaded_document_produces_rich_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            from repairgraph.intake.normalizer import normalize_intake_manifest
            manifest = _classify_doc(tmp)
            norm = tmp / "normalized"
            result = normalize_intake_manifest(manifest, output_dir=norm)
            assert result.written

            with patch("repairgraph.query.loader.NORMALIZED_DIR", norm):
                from repairgraph.review.routes import _build_model_for_vehicle
                model = _build_model_for_vehicle(
                    result.oem, result.year, result.model, result.operation
                )

            assert model is not None
            assert len(model.topology.zones) > 0
            assert len(model.state.actions) > 0
            assert len(model.state.qa_gates) > 0
            assert len(model.topology.zone_relationships) > 0
            uhss = [z for z in model.state.zones if z.material_classification == "UHSS"]
            assert uhss, "1470 MPa stiffener must surface as UHSS zone"
