# RepairGraph Graph Language Notes

## Observation

Honda repair procedures already encode machine-usable operational semantics.

The primary challenge is not OCR or document retrieval.

The primary challenge is defining a stable graph language capable of representing:

- structural topology
- joining relationships
- sectioning semantics
- replacement dependencies
- corrosion protection requirements
- material constraints
- procedural sequences

---

# Emerging Canonical Structure Node Types

## Structural Nodes

- panel
- separator
- stiffener
- rail
- gutter
- arch
- flange
- extension
- adapter
- reinforcement
- bracket
- pillar
- shelf
- bulkhead

---

# Emerging Relationship Types

## Spatial Relationships

- ADJACENT_TO
- JOINED_TO
- REINFORCES
- CONTAINS
- EXTENDS_FROM

## Procedural Relationships

- REQUIRES_REPLACEMENT
- INSPECT_IF_DAMAGED
- REQUIRES_SECTIONING
- REQUIRES_CORROSION_PROTECTION
- REQUIRES_ADHESIVE
- REQUIRES_WELDING_METHOD

## Material Relationships

- USES_MATERIAL
- REQUIRES_BRAZING
- REQUIRES_HSS_PROCEDURE
- REQUIRES_UHSS_PROCEDURE

---

# Important Insight

The procedures appear to contain two simultaneous graph systems:

1. Structural topology graph
2. Procedural dependency graph

These graphs overlap but are not identical.

This distinction may become foundational to RepairGraph architecture.
