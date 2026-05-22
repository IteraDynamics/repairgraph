# RepairGraph Evidence Model

## Purpose

RepairGraph produces structured advisory intelligence from normalized repair data.

As RepairGraph moves from extraction and graph construction into inference, every non-trivial output needs a clear answer to four questions:

1. What is this output based on?
2. How strong is that basis?
3. Does this output require OEM verification before use?
4. Is this an observed source fact, a normalized fact, or an inferred advisory signal?

The evidence model exists to prevent RepairGraph from becoming a black-box repair authority.

RepairGraph should remain a structured procedural intelligence system whose outputs preserve provenance, confidence, and verification requirements.

---

# Core Principle

RepairGraph outputs should distinguish between:

- source facts
- normalized facts
- derived graph relationships
- advisory inference
- corpus-pattern observations

These are not equivalent.

A replacement dependency directly normalized from a procedure is stronger than a corpus-gap signal inferred from other similar procedures.

A material classification from a construction diagram is stronger than a repair recommendation inferred from that material classification.

The evidence model makes those differences explicit.

---

# Evidence Object

The standard evidence object is:

```json
{
  "source_type": "normalized_procedure",
  "basis": ["procedure_dependency"],
  "confidence": "high",
  "requires_oem_verification": true,
  "interpretation": "advisory"
}
```

## Fields

### source_type

Describes the primary origin of the output.

Allowed values should include:

- `normalized_procedure`
- `normalized_structure`
- `normalized_taxonomy`
- `graph_relationship`
- `corpus_pattern`
- `derived_inference`
- `manual_review`

### basis

A list of basis tags explaining why the output exists.

Examples:

- `procedure_dependency`
- `joining_method_listed`
- `corrosion_requirement_listed`
- `vehicle_structure_material_map`
- `material_strength_at_or_above_uhss_threshold`
- `hss_material_strength_detected`
- `corpus_common_component`
- `corpus_universal_joining_method`
- `sectioning_location_present`

### confidence

A coarse confidence label.

Allowed values:

- `high`
- `medium`
- `low`
- `conditional`

Confidence should describe confidence in the structured signal, not certainty that a repair action is required in the real world.

### requires_oem_verification

Boolean.

For now, most inference outputs should set this to `true`.

RepairGraph should not imply that advisory inference replaces OEM procedure review.

### interpretation

Describes the kind of output.

Recommended values:

- `source_observation`
- `normalized_fact`
- `graph_relationship`
- `advisory`
- `corpus_pattern`

---

# Trust Semantics

## High Confidence

Use `high` when the output is directly represented in normalized procedure data.

Examples:

- a listed replacement dependency
- a listed joining method
- a listed corrosion requirement

High confidence does not mean the system can skip OEM verification.

It means the normalized RepairGraph object contains a direct signal.

## Medium Confidence

Use `medium` when the output is derived from a normalized fact.

Examples:

- material risk surfaced from tensile strength classification
- repair complexity derived from counts and weights
- QA review item derived from a material warning

## Conditional Confidence

Use `conditional` when the output depends on a repair condition.

Examples:

- `replace_if_sectioned`
- operation candidates triggered only when sectioning is performed

## Low Confidence

Use `low` sparingly for experimental heuristics.

Low-confidence outputs should not drive workflow decisions without review.

---

# Language Guidelines

RepairGraph should avoid unsupported authoritative language.

Avoid:

- `required` unless directly represented in source-normalized data
- `prohibited` unless directly source-grounded
- `missing` when describing corpus-pattern differences
- `must` unless quoting or directly representing source instruction

Prefer:

- `verify`
- `candidate`
- `advisory`
- `corpus gap`
- `review item`
- `source-grounded`
- `normalized signal`

---

# Examples

## Replacement Dependency

```json
{
  "item": "rear_pillar_separator",
  "reason": "replace_component",
  "category": "parts",
  "confidence": "high",
  "evidence": {
    "source_type": "normalized_procedure",
    "basis": ["procedure_dependency"],
    "confidence": "high",
    "requires_oem_verification": true,
    "interpretation": "normalized_fact"
  }
}
```

## UHSS Material Advisory

```json
{
  "component": "quarter_pillar_stiffener",
  "risk": "uhss_joining_constraint",
  "advisory": "UHSS material detected. Verify OEM-specified joining method for adjacent joins before repair planning or QA signoff.",
  "evidence": {
    "source_type": "normalized_structure",
    "basis": [
      "material_strength_at_or_above_uhss_threshold",
      "vehicle_structure_material_map"
    ],
    "confidence": "medium",
    "requires_oem_verification": true,
    "interpretation": "advisory"
  }
}
```

## Corpus Gap

```json
{
  "component": "wheel_arch_separator",
  "corpus_frequency": 0.8,
  "confidence": "high",
  "advisory": "Common in comparable procedures but not present in this normalized object. Verify applicability against the OEM source procedure.",
  "evidence": {
    "source_type": "corpus_pattern",
    "basis": ["corpus_common_component"],
    "confidence": "high",
    "requires_oem_verification": true,
    "interpretation": "corpus_pattern"
  }
}
```

---

# Strategic Importance

The evidence model is not administrative overhead.

It is core to RepairGraph's credibility.

The long-term product is not merely graph-native repair data.

The long-term product is trustworthy graph-native repair intelligence.
