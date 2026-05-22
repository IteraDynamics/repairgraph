from repairgraph.plan import build_repair_plan, reason_over_repair_plan
from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def test_reasoning_result_structure():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = _corpus_without("Accord")

    plan = build_repair_plan(proc, structure, corpus)
    reasoning = reason_over_repair_plan(plan)

    assert "findings" in reasoning
    assert "finding_count" in reasoning
    assert "by_severity" in reasoning


def test_critical_complexity_generates_triage_finding():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)
    reasoning = reason_over_repair_plan(plan)

    finding_types = [f["type"] for f in reasoning["findings"]]

    assert "complexity_triage" in finding_types


def test_uhss_generates_material_review_finding():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)
    reasoning = reason_over_repair_plan(plan)

    finding_types = [f["type"] for f in reasoning["findings"]]

    assert "material_joining_review" in finding_types


def test_conditional_operations_generate_finding():
    proc = load_procedure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc)
    reasoning = reason_over_repair_plan(plan)

    finding_types = [f["type"] for f in reasoning["findings"]]

    assert "conditional_operations" in finding_types


def test_sequencing_sensitive_repairs_generate_finding():
    proc = load_procedure("Honda", 2025, "CR-V")

    plan = build_repair_plan(proc)
    reasoning = reason_over_repair_plan(plan)

    finding_types = [f["type"] for f in reasoning["findings"]]

    assert "sequencing_controls" in finding_types


def test_reasoning_contains_high_severity_findings():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)
    reasoning = reason_over_repair_plan(plan)

    assert len(reasoning["by_severity"]["high"]) > 0
