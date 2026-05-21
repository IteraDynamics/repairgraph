# RepairGraph

RepairGraph is an AI-native procedural intelligence engine for collision repair.

The project transforms customer-authorized OEM repair procedures, construction/material diagrams, weld specifications, corrosion requirements, and structural repair information into structured, machine-readable repair graphs.

The goal is not to replace OEM procedures or redistribute OEM repair documentation. The goal is to create a structured intelligence layer that can power contextual workflows, operational copilots, spatial overlays, QA checks, and future wearable/AR repair guidance.

## Current focus

RepairGraph v0.1 begins with a narrow seed domain:

- OEM: Honda
- Model year: 2025
- Operation family: rear side outer panel / quarter panel replacement
- Supporting context: weld symbol definitions, corrosion protection, roof and side panel construction/material diagrams

## Core concepts

RepairGraph models collision repair as relationships between:

- OEM standards
- vehicle structure nodes
- material specifications
- joining methods
- sectioning locations
- corrosion protection requirements
- replacement dependencies
- procedural sequences
- spatial repair zones

## Repository status

This repository is in its foundation phase. The first milestone is to define the canonical ontology, normalize a small Honda procedure corpus into structured JSON, and validate that repair procedures can be represented as graph-compatible operational intelligence.

## What this is not

RepairGraph is not a PDF redistribution project, a generic document chatbot, or a replacement for OEM repair subscriptions. It is a transformation and reasoning layer for authorized repair information.
