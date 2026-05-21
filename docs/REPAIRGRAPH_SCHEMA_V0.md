# RepairGraph Canonical Schema v0

## Objective

RepairGraph represents collision repair procedures as structured procedural intelligence rather than static documentation.

This document defines the initial ontology primitives for RepairGraph v0.

---

# Core Entity Types

## OEMStandard

Defines OEM-wide semantic standards.

Examples:
- weld symbol definitions
- HSS/UHSS thresholds
- corrosion protection standards
- joining method rules
- adhesive semantics

---

## VehiclePlatform

Defines a specific vehicle configuration.

Examples:
- 2025 Honda CR-V
- 2025 Honda Civic Sedan
- 2025 Honda Pilot

Attributes:
- OEM
- year
- model
- trim/body style
- platform generation

---

## VehicleStructureNode

Represents a physical structural component or spatial repair zone.

Examples:
- rear side outer panel
- quarter pillar stiffener
- rear pillar gutter
- wheel arch separator
- roof rail

Attributes:
- material
- thickness
- tensile strength
- zinc treatment
- structural classification
- spatial relationships

---

## MaterialSpec

Defines material composition and strength.

Examples:
- 270 MPa steel
- 590 MPa HSS
- 980 MPa UHSS
- zinc-plated steel

Attributes:
- tensile strength
- coating
- repair restrictions
- weld compatibility

---

## JoiningMethod

Defines structural joining operations.

Examples:
- 2-plate spot weld
- MAG plug weld
- MIG brazing
- adhesive bonding

Attributes:
- weld type
- plate count
- material compatibility
- operation constraints

---

## RepairOperation

Defines a procedural repair workflow.

Examples:
- rear side outer panel replacement
- wheel arch separator replacement
- rear gutter sectioning

Attributes:
- operation sequence
- required tools
- required joins
- dependencies
- verification requirements

---

## SectioningLocation

Defines approved cut or sectioning locations.

Attributes:
- dimensional references
- adjacent structures
- allowed joining methods
- restrictions

---

## CorrosionRequirement

Defines anti-rust, sealer, foam, and undercoating requirements.

Examples:
- seam sealer
- urethane foam replacement
- undercoating application

---

## Dependency

Defines operational or structural relationships.

Examples:
- requires replacement
- adjacent to
- depends on
- inspect if damaged
- calibration required

---

# Initial Relationship Types

- USES_MATERIAL
- JOINS_WITH
- REQUIRES_OPERATION
- SECTIONS_AT
- PROTECT_WITH
- ADJACENT_TO
- REPLACES_WITH
- DEPENDS_ON
- REQUIRES_INSPECTION
- REQUIRES_CALIBRATION

---

# Initial Milestone

The first RepairGraph milestone is:

1. Normalize Honda quarter panel procedures into structured JSON
2. Normalize roof and side panel construction diagrams
3. Normalize weld symbol semantics
4. Build graph-compatible procedural representations
5. Validate ontology consistency across Honda vehicle platforms
