from repairgraph.plan import build_repair_plan
from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def test_repair_plan_structure():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = _corpus_without("Accord")

    plan = build_repair_plan(proc, structure, corpus)

    assert "repair_complexity" in plan
    assert "operation_sequence" in plan
    assert "supplement_candidates" in plan
    assert "material_risks" in plan
    assert "corpus_gap_analysis" in plan
    assert "qa_checklist" in plan
    assert "reasoning" in plan
    assert "summary" in plan


def test_repair_plan_metadata():
    proc = load_procedure("Honda", 2025, "CR-V")
    plan = build_repair_plan(proc)

    assert plan["model"] == "CR-V"
    assert plan["oem"] == "Honda"
    assert plan["year"] == 2025


def test_repair_plan_summary_counts():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)

    summary = plan["summary"]

    assert summary["risk_flag_count"] >= 0
    assert summary["supplement_candidate_count"] >= 0
    assert summary["qa_check_count"] >= 0


def test_repair_plan_without_structure_or_corpus():
    proc = load_procedure("Honda", 2025, "Civic")

    plan = build_repair_plan(proc)

    assert plan["material_risks"] is None
    assert plan["corpus_gap_analysis"] is None


def test_repair_plan_complexity_matches_source_module():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)

    assert plan["repair_complexity"]["tier"] == "critical"


def test_repair_plan_contains_phases():
    proc = load_procedure("Honda", 2025, "CR-V")

    plan = build_repair_plan(proc)

    phases = plan["operation_sequence"]["phases"]

    assert len(phases) > 0


def test_repair_plan_contains_qa_checks():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)

    assert plan["qa_checklist"]["total_checks"] > 0


def test_repair_plan_contains_reasoning_findings():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = _corpus_without("Accord")

    plan = build_repair_plan(proc, structure, corpus)

    reasoning = plan["reasoning"]

    assert reasoning["finding_count"] > 0
    assert len(reasoning["findings"]) > 0
