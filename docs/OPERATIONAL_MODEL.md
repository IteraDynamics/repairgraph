# RepairGraph Operational Model

## Purpose

The `OperationalModel` is the canonical artifact produced by RepairGraph.

It represents the result of compiling customer-supplied repair information into structured operational intelligence.

The model is intentionally distinct from source documents. It should not be treated as a replacement for OEM procedures or third-party repair information systems. Instead, it is the derived structure RepairGraph uses to power viewers, insights, replay, reports, QA workflows, and APIs.

---

## Conceptual Pipeline

```text
Customer-supplied repair information
              ↓
            Intake
              ↓
       Role classification
              ↓
      Evidence extraction
              ↓
   RepairGraph Compiler
              ↓
      OperationalModel
              ↓
Insights · Viewer · Replay · Reports · APIs
```

The source material is customer-owned.

The durable RepairGraph artifact is the operational model.

---

## Product Definition

An `OperationalModel` answers four questions:

1. What matters?
2. What is missing?
3. What is blocked?
4. What should happen next?

Every downstream product surface should consume this model instead of independently interpreting source repair documents.

---

## Non-Goals

The `OperationalModel` is not:

- an OEM procedure library
- a document repository
- a PDF archive
- an estimating database
- a substitute for OEM repair information
- a certified repair record
- proof of OEM compliance

It is an advisory operational representation derived from customer-provided repair information.

---

## Top-Level Shape

The exact Python schema can evolve, but conceptually the model should contain these sections:

```text
OperationalModel
├── model_metadata
├── source_manifest
├── repair_context
├── intake_summary
├── evidence_summary
├── topology
├── workflow
├── qa
├── blockers
├── state
├── replay
├── insights
├── exports
└── advisory
```

---

## model_metadata

Describes the model itself.

Recommended fields:

- `model_id`
- `schema_name`
- `schema_version`
- `generated_at`
- `generated_by`
- `compiler_version`
- `source_hashes`
- `advisory`

Purpose:

- Identify the operational model.
- Make outputs reproducible.
- Support versioned migrations.
- Confirm that the model is advisory.

---

## source_manifest

Describes the customer-supplied inputs without becoming a source document archive.

Recommended fields:

- `source_count`
- `source_types`
- `filenames`
- `content_hashes`
- `detected_roles`
- `missing_roles`
- `readability_status`
- `extraction_warnings`
- `customer_owned_content_notice`

Avoid storing:

- full PDFs
- page images
- proprietary diagrams
- long verbatim text from OEM or subscription materials

Purpose:

- Preserve auditability.
- Track what was analyzed.
- Avoid becoming a document repository.

---

## repair_context

Describes the repair being modeled.

Recommended fields:

- `oem`
- `year`
- `model`
- `trim`
- `operation`
- `repair_area`
- `vehicle_systems`
- `structural_involvement`
- `calibration_relevance`
- `confidence`

Purpose:

- Establish what repair the model represents.
- Provide context for all downstream reasoning.

---

## intake_summary

Summarizes document classification and readiness.

Recommended fields:

- `readiness`
- `overall_confidence`
- `file_count`
- `readable_file_count`
- `document_roles_detected`
- `document_roles_missing`
- `low_confidence_files`
- `conflicting_metadata`
- `diagnostics`

Purpose:

- Determine whether the uploaded packet is usable.
- Surface missing document categories before work begins.

---

## evidence_summary

Carries minimal explainable evidence forward.

Recommended fields:

- `evidence_items`
- `role_evidence`
- `material_evidence`
- `operation_evidence`
- `qa_evidence`
- `confidence_by_category`
- `requires_oem_verification`

Each evidence item should prefer:

- source identifier
- document role
- page or section reference when available
- short bounded evidence summary
- extraction method
- confidence

Purpose:

- Explain why RepairGraph reached a conclusion.
- Support review without storing the source document itself.

---

## topology

Represents the spatial and structural repair map.

Recommended fields:

- `zones`
- `regions`
- `adjacency`
- `material_by_zone`
- `operations_by_zone`
- `qa_by_zone`
- `blockers_by_zone`
- `visualization_payload`

Purpose:

- Connect procedural work to physical vehicle areas.
- Power topology viewer, AR payloads, and region-level QA.

---

## workflow

Represents the ordered repair process.

Recommended fields:

- `phases`
- `actions`
- `dependencies`
- `next_recommended_actions`
- `blocked_actions`
- `completed_actions`
- `workflow_readiness`

Purpose:

- Convert static procedure data into executable repair flow.
- Determine what can happen now and what must wait.

---

## qa

Represents quality gates and verification requirements.

Recommended fields:

- `qa_gates`
- `open_qa_gates`
- `passed_qa_gates`
- `blocking_qa_gates`
- `qa_by_phase`
- `qa_by_zone`
- `qa_severity_counts`
- `requires_technician_verification`

Purpose:

- Make required verification explicit.
- Prevent downstream phases from advancing before critical checks are resolved.

---

## blockers

Represents conditions preventing progress.

Recommended fields:

- `open_blockers`
- `resolved_blockers`
- `critical_blockers`
- `blockers_by_phase`
- `blockers_by_action`
- `blockers_by_zone`
- `blocking_reason`
- `recommended_resolution`

Purpose:

- Explain why a repair cannot advance.
- Help managers triage work.

---

## state

Represents the current state of the repair.

Recommended fields:

- `session_status`
- `current_phase`
- `phase_states`
- `action_states`
- `zone_states`
- `qa_gate_states`
- `blocker_states`
- `repair_readiness`
- `operational_confidence`

Purpose:

- Provide the live operational view of the repair.
- Support dashboards, reports, and technician workflow.

---

## replay

Represents the event history and state reconstruction path.

Recommended fields:

- `events`
- `replay_steps`
- `state_diffs`
- `event_significance`
- `actors`
- `timestamps`

Purpose:

- Reconstruct what happened.
- Explain why the state changed.
- Support audit trails and dispute resolution.

---

## insights

Represents prioritized operational findings.

Recommended fields:

- `overall_status`
- `top_findings`
- `all_findings`
- `critical_count`
- `high_count`
- `medium_count`
- `recommended_next_action`
- `executive_summary`

Each finding should include:

- `severity`
- `category`
- `title`
- `explanation`
- `recommended_action`
- `supporting_evidence`
- `confidence`

Purpose:

- Tell users what matters.
- Reduce cognitive load.
- Make RepairGraph feel like an experienced production manager reviewing the repair.

---

## exports

Describes available derived outputs.

Recommended fields:

- `technician_workflow_url`
- `repair_audit_trail_url`
- `executive_summary_url`
- `operational_model_url`
- `topology_viewer_url`
- `intake_analysis_url`

Purpose:

- Make derived artifacts portable.
- Keep source documents separate from operational outputs.

---

## advisory

Carries product and legal disclaimers in machine-readable form.

Recommended fields:

- `is_advisory`
- `requires_oem_verification`
- `requires_qualified_technician_review`
- `does_not_replace_oem_procedure`
- `does_not_certify_repair_completion`
- `customer_owned_source_content`

Purpose:

- Ensure downstream surfaces preserve the correct legal and operational posture.

---

## Persistence Boundary

RepairGraph should persist the `OperationalModel` and its derived outputs.

RepairGraph should not need to persist the original source documents.

Recommended persistent artifacts:

- operational model JSON
- insight payload
- workflow state
- event ledger
- report HTML
- source manifest
- source hashes
- evidence summaries

Avoid persistent storage of:

- full OEM procedures
- complete subscription provider content
- full diagrams or page images
- large verbatim copyrighted excerpts

---

## Compiler Responsibilities

The RepairGraph compiler should be responsible for:

1. Accepting customer-supplied source material.
2. Running intake and classification.
3. Building a source manifest.
4. Extracting minimal structured evidence.
5. Building topology.
6. Building workflow phases and actions.
7. Deriving QA gates and blockers.
8. Initializing repair state.
9. Generating replay structures.
10. Producing prioritized insights.
11. Returning a canonical `OperationalModel`.

The compiler should not:

- claim source ownership
- retain source documents unnecessarily
- generate unexplainable repair decisions
- bypass OEM verification
- duplicate downstream rendering logic

---

## Downstream Consumers

The following should consume the `OperationalModel`:

- Golden Path Demo
- Review Repair experience
- Insight Engine
- Topology Viewer
- HTML Reports
- Replay Reports
- Executive Summary
- AR/workflow payloads
- APIs
- future integrations

Downstream consumers should not re-parse source documents.

---

## Review Repair

The preferred front door for the product should eventually be:

```text
Review Repair
```

That action should compile customer-supplied repair information into an `OperationalModel` and present:

- overall readiness
- operational confidence
- critical risks
- missing document categories
- open blockers
- QA requirements
- next recommended action
- supporting evidence

This is the user-facing expression of the compiler architecture.

---

## Guiding Sentence

RepairGraph works with the repair information customers already license, compiles it into an operational model, and tells the shop what matters before costly mistakes happen.
