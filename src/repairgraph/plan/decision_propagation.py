def propagate_repair_decisions(plan: dict) -> dict:
    """
    Surface downstream consequences implied by repair-plan state.

    This layer answers questions such as:
    - Which decisions trigger additional parts/labor/QA review?
    - Which repair states have downstream consequences?
    - Which operational risks should be reviewed before estimate finalization?

    Outputs are advisory propagation signals derived from the synthesized repair plan.
    """

    decisions = []

    supplements = plan.get("supplement_candidates", {})
    qa = plan.get("qa_checklist", {})
    material_risks = plan.get("material_risks") or {}
    sequence = plan.get("operation_sequence", {})
    reasoning = plan.get("reasoning", {})

    supplement_items = supplements.get("supplement_candidates", [])
    qa_checks = qa.get("checks", [])
    phases = sequence.get("phases", [])
    phase_names = [p.get("name") for p in phases]

    conditional_items = [
        item for item in supplement_items
        if item.get("confidence") == "conditional"
    ]
    if conditional_items:
        decisions.append({
            "decision": "sectioning_or_conditional_repair_path",
            "trigger": "conditional_supplement_candidate_present",
            "state": "requires_review",
            "downstream_effects": {
                "parts": [item.get("item") for item in conditional_items if item.get("category") == "parts"],
                "labor": [item.get("item") for item in conditional_items if item.get("category") == "labor"],
                "qa_controls": [
                    check.get("check") for check in qa_checks
                    if check.get("conditional") is True
                ],
            },
            "review_question": "Does the actual repair path trigger the conditional replacement or labor item?",
            "basis": ["supplement_candidates", "qa_checklist"],
        })

    uhss_components = [
        item.get("component") for item in material_risks.get("material_risks", [])
        if item.get("risk") == "uhss_joining_constraint"
    ]
    if uhss_components:
        decisions.append({
            "decision": "uhss_adjacent_joining_path",
            "trigger": "uhss_material_risk_present",
            "state": "requires_oem_joining_verification",
            "downstream_effects": {
                "components": uhss_components,
                "qa_controls": [
                    check.get("check") for check in qa_checks
                    if check.get("category") == "material_compliance"
                ],
                "supplement_candidates": [
                    item.get("item") for item in supplement_items
                    if item.get("item") == "mig_brazing_labor"
                ],
            },
            "review_question": "Which adjacent joins interact with UHSS zones and which OEM-approved method applies?",
            "basis": ["material_risks", "qa_checklist", "supplement_candidates"],
        })

    if "corrosion_protection" in phase_names:
        corrosion_checks = [
            check.get("check") for check in qa_checks
            if check.get("category") == "corrosion_protection"
        ]
        corrosion_candidates = [
            item.get("item") for item in supplement_items
            if item.get("category") == "materials_and_labor"
        ]
        if corrosion_checks or corrosion_candidates:
            decisions.append({
                "decision": "post_joining_corrosion_protection_path",
                "trigger": "corrosion_protection_phase_present",
                "state": "requires_material_and_process_verification",
                "downstream_effects": {
                    "materials_and_labor": corrosion_candidates,
                    "qa_controls": corrosion_checks,
                },
                "review_question": "Have corrosion protection operations and materials been included and documented after joining?",
                "basis": ["operation_sequence", "supplement_candidates", "qa_checklist"],
            })

    high_reasoning = reasoning.get("by_severity", {}).get("high", [])
    if high_reasoning:
        decisions.append({
            "decision": "high_severity_repair_plan_review",
            "trigger": "high_severity_reasoning_findings_present",
            "state": "requires_estimator_or_repair_planner_review",
            "downstream_effects": {
                "finding_types": [finding.get("type") for finding in high_reasoning],
                "recommended_reviews": [finding.get("recommended_review") for finding in high_reasoning],
            },
            "review_question": "Have all high-severity advisory findings been reviewed before estimate or repair-plan finalization?",
            "basis": ["reasoning"],
        })

    return {
        "model": plan.get("model"),
        "oem": plan.get("oem"),
        "year": plan.get("year"),
        "operation": plan.get("operation"),
        "decision_count": len(decisions),
        "decisions": decisions,
        "by_state": {
            "requires_review": [d for d in decisions if d.get("state") == "requires_review"],
            "requires_oem_joining_verification": [
                d for d in decisions if d.get("state") == "requires_oem_joining_verification"
            ],
            "requires_material_and_process_verification": [
                d for d in decisions if d.get("state") == "requires_material_and_process_verification"
            ],
            "requires_estimator_or_repair_planner_review": [
                d for d in decisions if d.get("state") == "requires_estimator_or_repair_planner_review"
            ],
        },
        "interpretation_note": (
            "Decision-propagation outputs are advisory downstream consequence signals "
            "derived from the synthesized repair plan. They do not replace OEM procedure review."
        ),
    }
