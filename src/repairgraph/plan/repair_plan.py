from repairgraph.inference.material_risk import surface_material_risks
from repairgraph.inference.missing_operations import detect_missing_operations
from repairgraph.inference.qa_checklist import generate_qa_checklist
from repairgraph.inference.repair_complexity import score_repair_complexity
from repairgraph.inference.sequencing import build_operation_sequence
from repairgraph.inference.supplement_candidates import infer_supplement_candidates
from repairgraph.plan.decision_propagation import propagate_repair_decisions
from repairgraph.plan.reasoning import reason_over_repair_plan


def build_repair_plan(
    procedure: dict,
    structure: dict | None = None,
    corpus: list[dict] | None = None,
) -> dict:
    """
    Synthesize a structured repair-plan object from normalized procedure data
    and RepairGraph inference modules.

    This is not an execution engine.

    It is a graph-native operational planning layer intended to:
    - organize procedural workflow
    - surface risk
    - identify supplements
    - preserve provenance
    - structure QA review
    - support future AI-assisted reasoning
    """

    sequence = build_operation_sequence(procedure)
    complexity = score_repair_complexity(procedure, structure)
    supplements = infer_supplement_candidates(procedure, structure)
    qa = generate_qa_checklist(procedure, structure, corpus)

    material_risks = None
    if structure:
        material_risks = surface_material_risks(procedure, structure)

    corpus_gaps = None
    if corpus:
        corpus_gaps = detect_missing_operations(procedure, corpus)

    plan = {
        "plan_version": "0.1",
        "model": procedure.get("model"),
        "oem": procedure.get("oem"),
        "year": procedure.get("year"),
        "operation": procedure.get("operation"),
        "repair_complexity": complexity,
        "operation_sequence": sequence,
        "supplement_candidates": supplements,
        "material_risks": material_risks,
        "corpus_gap_analysis": corpus_gaps,
        "qa_checklist": qa,
        "summary": {
            "complexity_tier": complexity.get("tier"),
            "risk_flag_count": len(complexity.get("risk_flags", [])),
            "supplement_candidate_count": supplements.get("total", 0),
            "qa_check_count": qa.get("total_checks", 0),
            "critical_qa_count": len(
                qa.get("by_priority", {}).get("critical", [])
            ),
        },
        "interpretation_note": (
            "Repair-plan synthesis outputs are structured advisory planning artifacts "
            "derived from normalized RepairGraph data and inference modules. "
            "All operations must be verified against the applicable OEM repair procedure."
        ),
    }

    plan["reasoning"] = reason_over_repair_plan(plan)
    plan["decision_propagation"] = propagate_repair_decisions(plan)

    return plan
