# RepairGraph Architectural Principles

## Purpose

This document defines the architectural boundaries RepairGraph should preserve as the product evolves.

RepairGraph is an operational intelligence layer for procedural repair work. It is not a document repository, OEM data provider, estimating platform, or replacement for licensed repair information systems.

These principles exist to keep the implementation aligned with the product vision, legal posture, and long-term platform strategy.

---

## 1. Customer-Owned Content

RepairGraph works with repair information supplied by the customer.

Customers are responsible for ensuring they have the right to access and use the OEM, subscription, or third-party repair information they provide to RepairGraph.

RepairGraph should not distribute, resell, republish, or permanently maintain OEM repair documentation or third-party subscription content.

The product should be positioned as a tool that helps customers operationalize the repair information they already license.

### Design implication

Source documents are inputs, not the product.

RepairGraph may analyze customer-supplied documents to derive an operational model, but the original documents should remain customer-controlled.

Where possible, source documents should be processed transiently and discarded after the derived operational model has been created, unless a customer explicitly chooses to retain them in their own environment.

---

## 2. Operationalization, Not Replacement

RepairGraph does not replace OEM repair information.

RepairGraph operationalizes it.

The system should always treat OEM procedures and authorized repair information as the source of truth for technical repair requirements.

RepairGraph's role is to convert static procedural information into:

- workflow phases
- procedural dependencies
- QA gates
- blockers
- topology
- replayable state
- repair readiness signals
- operational insights
- recommended next actions

### Design implication

RepairGraph outputs should be advisory workflow intelligence.

They should not claim to certify repair completion, OEM compliance, or repair quality.

Qualified technician review and OEM procedure verification remain required.

---

## 3. Derived Models Are the Persistent Artifact

The durable RepairGraph artifact is the operational model, not the source document.

RepairGraph should persist derived structures such as:

- repair metadata
- document role classifications
- extraction confidence
- evidence summaries
- repair topology
- workflow phases
- action states
- QA gates
- blockers
- event history
- replay steps
- insight findings
- exportable reports

RepairGraph should avoid persisting:

- full OEM PDFs
- OEM page images
- large copyrighted text blocks
- diagrams from proprietary repair systems
- subscription provider content reproduced verbatim

### Design implication

Evidence references should be minimal, structured, and explainable.

Where RepairGraph needs to support auditability, it should prefer source references, hashes, document role metadata, page numbers, short snippets within lawful limits, and customer-controlled links rather than storing full source content.

---

## 4. The Compiler Boundary

RepairGraph should be organized around a clear compiler boundary.

Customer-supplied repair information enters the system as source material.

RepairGraph compiles that material into a canonical operational model.

Downstream features consume the operational model.

```text
Customer-supplied repair information
              ↓
       RepairGraph Compiler
              ↓
      Operational Model
              ↓
Viewer · Insights · Replay · Reports · APIs
```

### Design implication

Intake, classification, extraction, topology, workflow, QA, state, replay, and insights should converge on a stable operational model interface.

Downstream features should not independently parse source documents or recreate domain logic.

---

## 5. Deterministic Before Generative

RepairGraph should prefer deterministic reasoning wherever possible.

The product's value depends on trust, auditability, and repeatability.

For repair workflows, confidence comes from being able to explain why the system produced a finding.

### Design implication

Insights should include:

- severity
- category
- title
- explanation
- recommended action
- supporting evidence
- confidence

If generative AI is introduced later, it should summarize or assist around deterministic outputs rather than silently creating repair decisions.

---

## 6. Explainability Is a Product Requirement

Every important recommendation should be explainable.

RepairGraph should be able to answer:

- Why is this repair blocked?
- Why is this QA gate required?
- Why is this the next recommended action?
- What evidence supports this finding?
- What document category or workflow state produced this result?

### Design implication

Internal models should carry provenance and evidence summaries forward.

The system should not collapse complex reasoning into opaque scores.

---

## 7. Reduce Cognitive Load

RepairGraph should not simply expose more data.

Repair professionals already have too much information to process.

RepairGraph should prioritize what matters.

### Design implication

Product surfaces should lead with:

- critical risks
- missing documentation categories
- open blockers
- workflow readiness
- next recommended action
- confidence and evidence

Counts, raw lists, logs, and detailed tables should remain available, but secondary.

---

## 8. Collision Repair Is the Wedge

RepairGraph begins in collision repair because the domain is complex, high-stakes, document-heavy, and operationally fragmented.

The underlying architecture should remain broader than collision repair.

At its core, RepairGraph transforms procedural documentation into operational intelligence.

### Design implication

Domain-specific modules should exist, but the core architecture should avoid unnecessary assumptions that only make sense for automotive collision repair.

The long-term platform should be capable of supporting other procedural industries such as aviation maintenance, industrial service, energy infrastructure, medical equipment maintenance, and regulated inspection workflows.

---

## 9. Complement the Ecosystem

RepairGraph should complement OEM portals, ALLDATA, Mitchell, CCC, RepairLogic, and other repair information or estimating platforms.

It should make those systems more operationally useful.

It should not position itself as a replacement for licensed repair information.

### Design implication

Customer-facing language should emphasize:

> RepairGraph works with the repair information you already license.

Avoid language that implies RepairGraph owns, distributes, or replaces proprietary repair procedures.

---

## 10. Better Decisions Are the Product

Features are not the product.

Operational understanding is the product.

Every feature should help users make a better operational decision before a costly mistake happens.

Before adding new capabilities, ask:

1. Does this improve repair review?
2. Does this clarify what matters?
3. Does this reduce operational risk?
4. Does this strengthen the compiler-to-model architecture?
5. Does this avoid creating an OEM content repository?

If the answer is no, the feature should wait.
