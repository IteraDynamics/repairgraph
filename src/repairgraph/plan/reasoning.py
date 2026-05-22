def reason_over_repair_plan(plan: dict) -> dict:
    """
    Produce structured advisory reasoning findings from a synthesized repair plan.

    This layer does not create new source facts. It inspects the composed repair
    plan and surfaces planning implications, conditional triggers, QA drivers,
    supplement pressure points, and sequencing-critical phases.
    """

    findings = []

    complexity = plan.get("repair_complexity", {})
    sequence = plan.get("operation_sequence", {})
    supplements = plan.get("supplement_candidates", {})
    material_risks = plan.get("material_risks") or {}
    qa = plan.get("qa_checklist", {})
    corpus_gaps = plan.get("corpus_gap_analysis") or {}

    if complexity.get("tier") in ("high", "critical"):
        findings.append({
            "type": "complexity_triage",
            "severity": "high" if complexity.get("tier") == "critical" else "medium",
            "finding": f"Repair plan is classified as {complexity.get('tier')} complexity.",
            "drivers": complexity.get("risk_flags", []),
            "recommended_review": "Estimator and repair planner should review all high-impact dependencies before finalizing the repair plan.",
            "basis": ["repair_complexity"],
        })

    conditional_candidates = [
        c for c in supplements.get("supplement_candidates", [])
        if c.get("confidence") == "conditional"
    ]
    if conditional_candidates:
        findings.append({
            "type": "conditional_operations",
            "severity": "medium",
            "finding": "Repair plan contains conditionally triggered candidate operations or parts.",
            "items": [c.get("item") for c in conditional_candidates],
            "recommended_review": "Verify whether the triggering repair condition applies before adding or excluding these items.",
            "basis": ["supplement_candidates", "conditional_confidence"],
        })

    supplement_total = supplements.get("total", 0)
    if supplement_total >= 8:
        findings.append({
            "type": "supplement_density",
            "severity": "high",
            "finding": f"Repair plan contains {supplement_total} supplement candidate(s).",
            "recommended_review": "Review parts, materials, and labor candidates before estimate finalization.",
            "basis": ["supplement_candidates"],
        })

    uhss_risks = [
        r for r in material_risks.get("material_risks", [])
        if r.get("risk") == "uhss_joining_constraint"
    ]
    if uhss_risks:
        findings.append({
            "type": "material_joining_review",
            "severity": "high",
            "finding": "UHSS material zones are present and drive joining-method review.",
            "components": [r.get("component") for r in uhss_risks],
            "recommended_review": "Verify OEM-specified joining methods for all adjacent joins before welding or QA signoff.",
            "basis": ["material_risks"],
        })

    critical_qa = qa.get("by_priority", {}).get("critical", [])
    if critical_qa:
        findings.append({
            "type": "critical_qa_controls",
            "severity": "high",
            "finding": f"Repair plan contains {len(critical_qa)} critical QA control(s).",
            "checks": [c.get("check") for c in critical_qa],
            "recommended_review": "Critical QA controls should be explicitly documented before repair completion.",
            "basis": ["qa_checklist"],
        })

    phases = sequence.get("phases", [])
    phase_names = [p.get("name") for p in phases]
    sequencing_required = {
        "sectioning_preparation",
        "component_replacement",
        "panel_installation_and_joining",
        "corrosion_protection",
        "post_repair_verification",
    }
    if sequencing_required.intersection(phase_names):
        findings.append({
            "type": "sequencing_controls",
            "severity": "medium",
            "finding": "Repair plan contains sequencing-sensitive phases.",
            "phases": [p for p in phase_names if p in sequencing_required],
            "recommended_review": "Complete prerequisite inspections and replacement decisions before final joining and corrosion protection.",
            "basis": ["operation_sequence"],
        })

    total_gaps = corpus_gaps.get("total_gaps", 0)
    if total_gaps:
        findings.append({
            "type": "corpus_gap_review",
            "severity": "medium",
            "finding": f"Repair plan contains {total_gaps} corpus-pattern gap(s).",
            "recommended_review": "Treat corpus gaps as review prompts, not definitive OEM omissions.",
            "basis": ["corpus_gap_analysis"],
        })

    return {
        "model": plan.get("model"),
        "oem": plan.get("oem"),
        "year": plan.get("year"),
        "operation": plan.get("operation"),
        "finding_count": len(findings),
        "findings": findings,
        "by_severity": {
            "high": [f for f in findings if f.get("severity") == "high"],
            "medium": [f for f in findings if f.get("severity") == "medium"],
            "low": [f for f in findings if f.get("severity") == "low"],
        },
        "interpretation_note": (
            "Repair-plan reasoning outputs are advisory findings derived from an already synthesized "
            "RepairGraph repair plan. They do not replace OEM procedure review."
        ),
    }
