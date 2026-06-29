# Operational Planner Specification v1

## Purpose

The Operational Planner is the next reasoning layer in RepairGraph.

Its job is not to list findings, blockers, QA gates, or missing documents.

Its job is to answer one question:

> What is the highest-leverage action the shop should take next?

RepairGraph already compiles customer-supplied repair information into an `OperationalModel`. The Operational Planner consumes that model and turns workflow state, dependencies, QA gates, blockers, evidence, and insights into a prioritized plan of action.

This is a platform capability, not a collision-only feature.

Collision repair is the first product surface, but the same abstraction should apply to any procedural domain where work is constrained by dependencies, evidence, gates, and blocked downstream actions.

---

## Strategic Context

The product has evolved through several stages:

```text
Documents
  ↓
Intake
  ↓
Classification
  ↓
Workflow / Topology / State
  ↓
OperationalModel
  ↓
Insights
  ↓
Executive Review
  ↓
Root Cause Analysis
```

Root Cause Analysis revealed an important product distinction.

A root cause engine can explain why work is blocked.

A planner should determine what action creates the most operational progress.

Those are related, but not identical.

Example:

```text
Root Cause:
OEM joining verification unresolved.

Planner Recommendation:
Verify the OEM joining method at the quarter pillar stiffener now.
This is the highest-leverage next action because it unlocks panel installation, clears six QA gates, and allows downstream corrosion protection and final verification to proceed.
```

The product should move from:

> Here are the problems.

Toward:

> Do this next, because it unlocks the most work.

---

## Product Promise

The Operational Planner should help users understand:

1. What should happen next?
2. Why is that the best next action?
3. What becomes unblocked if it is completed?
4. What can wait?
5. What risk is reduced by doing it now?

The planner should make RepairGraph feel less like a dashboard and more like an experienced production manager prioritizing the repair.

---

## Non-Goals

The Operational Planner is not:

- a scheduling system
- a labor estimating engine
- a technician assignment engine
- an AI agent
- an LLM planner
- a replacement for OEM procedures
- a repair certification tool
- a project-management application

It should not claim to certify repair completion, compliance, quality, or safety.

It should produce advisory operational recommendations that require qualified technician review against current OEM procedures.

---

## Inputs

The planner should consume the canonical `OperationalModel`.

Primary inputs:

- workflow phases
- actions
- action states
- QA gates
- blockers
- dependencies
- topology zones
- material or domain-specific risk signals
- evidence summaries
- insights
- root cause analysis, if available
- advisory metadata

The planner should not re-parse source documents.

The planner should not directly depend on collision-specific objects unless accessed through a domain adapter or domain projection.

---

## Output Shape

Suggested primary object:

```text
OperationalPlan
├── plan_id
├── model_id
├── generated_at
├── overall_status
├── next_best_action
├── action_queue
├── critical_path
├── expected_unlocks
├── blocked_by
├── deferred_work
├── risk_reduction
├── confidence
├── supporting_evidence
└── advisory
```

---

## Core Concepts

### 1. Next Best Action

The single highest-leverage action that should happen next.

A next best action should include:

- `action_id`
- `display_label`
- `action_type`
- `domain_context`
- `why_now`
- `expected_unlocks`
- `risk_reduction`
- `required_evidence`
- `blocked_by`
- `confidence`
- `advisory_notice`

Example:

```text
Next Best Action:
Verify OEM joining method at quarter pillar stiffener.

Why now:
This clears the highest-impact blocking QA gate and allows panel installation to resume.

Expected unlock:
- Panel Installation and Joining
- 6 QA gates
- 1 blocked workflow phase
```

---

### 2. Critical Path

The sequence of actions or gates most constraining forward progress.

The critical path should represent the order in which work must be resolved to maximize progress.

Example:

```text
Verify Joining Method
  ↓
Clear Material Compliance QA
  ↓
Resume Panel Installation
  ↓
Complete Corrosion Protection QA
  ↓
Proceed to Final Verification
```

The critical path should be derived from dependencies, blockers, QA gates, phase ordering, and state.

---

### 3. Expected Unlocks

The concrete work that becomes available when the next best action is completed.

Expected unlocks may include:

- phases
- actions
- QA gates
- blocked zones
- reports
- downstream reviews
- domain-specific workflow states

Each unlock should be explainable.

Example:

```text
Completing this action unlocks:
- Panel Installation and Joining
- 5 joining compliance QA gates
- downstream corrosion protection review
```

---

### 4. Leverage Score

A numerical ranking used to compare candidate actions.

The score should not be shown as the primary product language, but it should be available for debugging and tests.

Suggested scoring inputs:

```text
Critical QA gate cleared             +100
High-priority QA gate cleared         +60
Blocked phase unblocked               +50 each
Blocked action unblocked              +10 each
Downstream QA gates enabled            +8 each
Material / safety risk reduced         +40
Compliance risk reduced                +30
Evidence gap resolved                  +20
Workflow moves to next phase           +25
Already completed / redundant action  -100
Action still blocked                  -80
Requires unavailable evidence          -50
```

Weights are implementation details and may evolve.

They must be documented and tested.

---

### 5. Effort Estimate

The planner may eventually estimate effort.

For v1, effort should be simple and deterministic.

Suggested categories:

- `quick_check`
- `document_review`
- `technician_verification`
- `physical_repair_action`
- `inspection_required`
- `external_dependency`

Do not invent exact labor times unless reliable data exists.

If a time estimate is shown, it should be clearly labeled as heuristic.

---

### 6. Risk Reduction

A qualitative explanation of what risk is reduced by completing the action.

Examples:

- structural non-compliance risk
- corrosion warranty risk
- documentation gap risk
- downstream rework risk
- final QA failure risk

Risk reduction should be derived from existing findings, QA gates, blockers, materials, and domain context.

---

## Planning Algorithm v1

The first implementation should be deterministic and conservative.

### Step 1: Build Candidate Actions

Candidate actions may come from:

- open blocking QA gates
- unresolved blockers
- next recommended workflow actions
- blocked phases
- root causes
- missing evidence/document categories
- open high-priority findings

Each candidate should be normalized into a generic action shape.

Example generic action:

```text
PlannerCandidate
├── candidate_id
├── type
├── display_label
├── source_entities
├── related_phase_ids
├── related_action_ids
├── related_qa_gate_ids
├── related_blocker_ids
├── related_findings
├── domain_context
└── advisory
```

---

### Step 2: Build Dependency Graph

The graph should represent operational constraints.

Nodes may include:

- workflow phases
- workflow actions
- QA gates
- blockers
- findings
- root causes
- evidence requirements

Edges may include:

- blocks
- depends_on
- unlocks
- verifies
- enables
- requires_evidence
- derived_from

For v1, the graph can be shallow and assembled from existing relationships.

The goal is not perfect graph theory.

The goal is to identify the action that unlocks the most meaningful downstream work.

---

### Step 3: Score Candidates

For each candidate, compute:

- blockers resolved
- QA gates cleared
- phases unblocked
- actions enabled
- findings reduced
- risk reduced
- whether required evidence is available
- whether candidate itself is blocked

Apply deterministic weights.

---

### Step 4: Select Next Best Action

Sort candidates by:

1. highest leverage score
2. severity of issue addressed
3. earliest workflow phase
4. greatest downstream unlock count
5. highest confidence

Return exactly one `next_best_action`.

If no strong candidate exists, return a conservative recommendation such as:

```text
Review repair packet completeness before proceeding.
```

---

### Step 5: Produce Action Queue

Return a short ordered queue.

Suggested shape:

```text
Today
1. Verify OEM joining method.
2. Clear material compliance QA gate.
3. Resume panel installation after QA approval.

Next
4. Complete corrosion protection verification.
5. Complete dimensional verification.
```

The page should show only the first one to three actions prominently.

Longer queues should be collapsible.

---

## Relationship to Root Cause Analysis

Root Cause Analysis explains why the repair is blocked.

Operational Planning decides what to do next.

The planner may consume root causes as one input, but it should not simply display root causes as recommendations.

Example distinction:

```text
Root Cause:
Corrosion protection requirements not cleared.

Planner Decision:
Do not address corrosion first, because panel installation is still blocked by unresolved joining verification.
```

This distinction is critical.

The planner must reason over sequence, not just categories.

---

## Relationship to Review Repair

The Review Repair page should eventually consume `OperationalPlan`.

Preferred structure:

```text
OperationalModel
      ↓
RootCauseAnalysis
      ↓
OperationalPlanner
      ↓
ExecutiveReview
      ↓
Review Repair UI
```

The Review page should not own planning logic.

The UI should present:

- current status
- next best action
- expected unlocks
- supporting evidence
- critical path
- role-specific messages
- advisory language

---

## Collision Product Example

Given:

- Quarter panel replacement
- UHSS quarter pillar stiffener
- open material compliance QA gate
- blocked panel installation phase
- blocked corrosion protection phase
- blocked post-repair verification

The planner should produce:

```text
Status:
Blocked

Next Best Action:
Verify OEM joining method at quarter pillar stiffener.

Why this action:
This is the highest-leverage unresolved gate. It blocks panel installation and prevents downstream corrosion protection and final verification from progressing.

Expected unlock:
- Panel Installation and Joining
- 6 joining/material QA gates
- downstream corrosion protection review

Technician message:
Before installing the quarter panel, confirm the approved OEM joining method for the quarter pillar stiffener. Do not continue joining until this gate is closed.

Manager message:
Confirm the joining specification and QA sign-off before assigning structural panel installation.
```

---

## Domain-Agnostic Example

Aviation maintenance:

```text
Next Best Action:
Complete torque verification for engine mount fasteners.

Why this action:
This verification blocks final inspection, closeout documentation, and release-to-service review.
```

Industrial maintenance:

```text
Next Best Action:
Complete lockout verification before pump disassembly.

Why this action:
This clears the safety gate required before mechanical work can begin.
```

Healthcare equipment maintenance:

```text
Next Best Action:
Run electrical safety test before returning device to service.

Why this action:
This verification blocks final release and regulatory documentation.
```

The same planner abstraction should apply across all of these.

---

## API Direction

Future endpoint:

```text
GET /internal/review/plan
```

Response:

```json
{
  "overall_status": "blocked",
  "next_best_action": {
    "display_label": "Verify OEM joining method at quarter pillar stiffener",
    "why_now": "This clears the highest-impact blocking QA gate and unlocks panel installation.",
    "expected_unlocks": [
      "Panel Installation and Joining",
      "6 QA gates",
      "Downstream corrosion protection review"
    ],
    "confidence": "high"
  },
  "critical_path": [...],
  "action_queue": [...],
  "advisory": {...}
}
```

---

## Testing Requirements

When implemented, tests should verify:

- next best action selection
- leverage scoring
- blocked phase unlock calculation
- QA gate unlock calculation
- root causes are not blindly copied into recommendations
- sequence beats category grouping
- completed actions are not recommended
- blocked actions are not recommended unless the recommendation is to clear their blocker
- collision adapter output still works
- generic/domain-agnostic model can produce a plan
- review page displays planner output without owning the algorithm

---

## Success Criteria

A production manager should be able to answer in under ten seconds:

- What do we do next?
- Why that action?
- What does it unlock?
- What can wait?

A technician should receive a clear, actionable instruction.

A manager should receive a clear verification responsibility.

The system should avoid overwhelming users with long lists of findings when one high-leverage action matters most.

---

## Guiding Principle

RepairGraph should not merely identify problems.

RepairGraph should identify the next highest-leverage action.

That is the difference between a checklist and an operational intelligence platform.
