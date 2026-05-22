from repairgraph.plan import build_repair_plan
from repairgraph.plan.decision_propagation import propagate_repair_decisions
from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def test_decision_propagation_structure():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = _corpus_without("Accord")

    plan = build_repair_plan(proc, structure, corpus)
    propagation = propagate_repair_decisions(plan)

    assert "decisions" in propagation
    assert "decision_count" in propagation
    assert "by_state" in propagation


def test_conditional_repair_path_detected():
    proc = load_procedure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc)
    propagation = propagate_repair_decisions(plan)

    decision_types = [d["decision"] for d in propagation["decisions"]]

    assert "sectioning_or_conditional_repair_path" in decision_types


def test_uhss_joining_path_detected():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)
    propagation = propagate_repair_decisions(plan)

    decision_types = [d["decision"] for d in propagation["decisions"]]

    assert "uhss_adjacent_joining_path" in decision_types


def test_corrosion_path_detected():
    proc = load_procedure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc)
    propagation = propagate_repair_decisions(plan)

    decision_types = [d["decision"] for d in propagation["decisions"]]

    assert "post_joining_corrosion_protection_path" in decision_types


def test_high_severity_review_detected():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)
    propagation = propagate_repair_decisions(plan)

    decision_types = [d["decision"] for d in propagation["decisions"]]

    assert "high_severity_repair_plan_review" in decision_types


def test_repair_plan_contains_decision_propagation():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    plan = build_repair_plan(proc, structure)

    assert "decision_propagation" in plan
    assert plan["decision_propagation"]["decision_count"] > 0
