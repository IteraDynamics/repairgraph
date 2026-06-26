"""Tests for the canonical OperationalModel and its sub-schemas."""
from __future__ import annotations

import pytest

from repairgraph.core.operational_model import (
    AdvisoryNotice,
    DomainContext,
    EvidenceSummary,
    ExportLinks,
    ModelMetadata,
    OperationalModel,
    ReplaySummary,
    SourceManifest,
    WorkflowSummary,
)


class TestModelMetadata:
    def test_create_generates_unique_ids(self):
        a = ModelMetadata.create()
        b = ModelMetadata.create()
        assert a.model_id != b.model_id

    def test_create_sets_schema_name(self):
        m = ModelMetadata.create()
        assert m.schema_name == "repairgraph.core.operational_model"

    def test_create_advisory_true(self):
        m = ModelMetadata.create()
        assert m.advisory is True

    def test_to_dict_has_required_keys(self):
        m = ModelMetadata.create()
        d = m.to_dict()
        for key in ("model_id", "schema_name", "schema_version", "generated_at", "generated_by", "advisory"):
            assert key in d, f"Missing key: {key}"


class TestSourceManifest:
    def test_defaults(self):
        sm = SourceManifest()
        assert sm.source_count == 0
        assert sm.readiness == "incomplete"

    def test_to_dict_serializes_fields(self):
        sm = SourceManifest(source_count=3, filenames=["a.txt"], readiness="ready")
        d = sm.to_dict()
        assert d["source_count"] == 3
        assert d["filenames"] == ["a.txt"]
        assert d["readiness"] == "ready"

    def test_customer_owned_notice_present(self):
        sm = SourceManifest()
        d = sm.to_dict()
        assert "customer_owned_content_notice" in d
        assert len(d["customer_owned_content_notice"]) > 20


class TestDomainContext:
    def test_to_dict_includes_domain(self):
        dc = DomainContext(domain="collision_repair", display_label="Test", context_data={"foo": "bar"})
        d = dc.to_dict()
        assert d["domain"] == "collision_repair"
        assert d["context_data"]["foo"] == "bar"


class TestAdvisoryNotice:
    def test_all_advisory_flags_true(self):
        notice = AdvisoryNotice()
        assert notice.is_advisory is True
        assert notice.requires_oem_verification is True
        assert notice.requires_qualified_technician_review is True
        assert notice.does_not_replace_oem_procedure is True
        assert notice.does_not_certify_repair_completion is True
        assert notice.customer_owned_source_content is True

    def test_to_dict_has_notice_text(self):
        d = AdvisoryNotice().to_dict()
        assert "notice" in d
        assert len(d["notice"]) > 20


class TestOperationalModel:
    def _make_model(self) -> OperationalModel:
        return OperationalModel(
            metadata=ModelMetadata.create(),
            source_manifest=SourceManifest(),
            domain_context=DomainContext(domain="test"),
            evidence=EvidenceSummary(),
            topology=None,
            state=None,
            workflow=WorkflowSummary(),
            replay=ReplaySummary(),
            insights=None,
            exports=ExportLinks(),
        )

    def test_construction(self):
        model = self._make_model()
        assert model.metadata is not None
        assert model.advisory is not None

    def test_to_dict_has_all_sections(self):
        model = self._make_model()
        d = model.to_dict()
        for section in ("metadata", "source_manifest", "domain_context", "evidence",
                        "topology", "state", "workflow", "replay", "insights",
                        "exports", "advisory"):
            assert section in d, f"Missing section: {section}"

    def test_to_dict_schema_name(self):
        d = self._make_model().to_dict()
        assert d["schema_name"] == "repairgraph.core.operational_model"

    def test_advisory_notice_in_dict(self):
        d = self._make_model().to_dict()
        assert d["advisory"]["is_advisory"] is True
