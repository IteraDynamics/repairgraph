"""
SVG vehicle silhouette layout definitions for the topology viewer.

Defines the geometric panel regions, their SVG paths, and their mapping to
RepairGraph zone_ids. The vehicle is rendered as a simplified side-profile
SVG with labeled repair regions.

All coordinates use a 900×340 viewBox. Regions are clickable SVG elements.
"""
from __future__ import annotations

# Each region maps:
#   id         - unique region id used in SVG and JS
#   label      - display label
#   zone_keys  - partial zone_id substrings to match against RepairState zones
#   d          - SVG path or rect definition (as dict with type/attrs)
#   cx, cy     - label anchor point
VEHICLE_REGIONS: list[dict] = [
    {
        "id": "region_hood",
        "label": "Hood",
        "zone_keys": ["hood", "front_panel", "front_upper"],
        "shape": "rect",
        "x": 38, "y": 78, "width": 145, "height": 80,
        "rx": 6,
        "cx": 110, "cy": 120,
    },
    {
        "id": "region_front_bumper",
        "label": "Front Bumper",
        "zone_keys": ["front_bumper", "bumper_cover_front", "front_lower"],
        "shape": "rect",
        "x": 10, "y": 158, "width": 62, "height": 48,
        "rx": 4,
        "cx": 41, "cy": 183,
    },
    {
        "id": "region_front_door",
        "label": "Front Door",
        "zone_keys": ["front_door", "door_front", "door_panel_front"],
        "shape": "rect",
        "x": 198, "y": 78, "width": 158, "height": 130,
        "rx": 4,
        "cx": 277, "cy": 143,
    },
    {
        "id": "region_rear_door",
        "label": "Rear Door",
        "zone_keys": ["rear_door", "door_rear", "door_panel_rear"],
        "shape": "rect",
        "x": 362, "y": 78, "width": 130, "height": 130,
        "rx": 4,
        "cx": 427, "cy": 143,
    },
    {
        "id": "region_front_quarter",
        "label": "Front Quarter",
        "zone_keys": ["front_quarter", "quarter_front", "fender", "front_fender"],
        "shape": "rect",
        "x": 72, "y": 78, "width": 122, "height": 130,
        "rx": 4,
        "cx": 133, "cy": 143,
    },
    {
        "id": "region_rear_quarter",
        "label": "Rear Quarter",
        "zone_keys": ["rear_quarter", "quarter_rear", "quarter_panel", "c_pillar_outer", "d_pillar"],
        "shape": "rect",
        "x": 498, "y": 78, "width": 148, "height": 130,
        "rx": 4,
        "cx": 572, "cy": 143,
    },
    {
        "id": "region_roof",
        "label": "Roof",
        "zone_keys": ["roof", "roof_panel", "roof_outer", "headliner"],
        "shape": "rect",
        "x": 198, "y": 38, "width": 448, "height": 44,
        "rx": 6,
        "cx": 422, "cy": 61,
    },
    {
        "id": "region_rocker",
        "label": "Rocker",
        "zone_keys": ["rocker", "sill", "rocker_panel", "side_sill"],
        "shape": "rect",
        "x": 148, "y": 208, "width": 468, "height": 28,
        "rx": 3,
        "cx": 382, "cy": 223,
    },
    {
        "id": "region_rear_bumper",
        "label": "Rear Bumper",
        "zone_keys": ["rear_bumper", "bumper_cover_rear", "rear_lower"],
        "shape": "rect",
        "x": 718, "y": 158, "width": 62, "height": 48,
        "rx": 4,
        "cx": 749, "cy": 183,
    },
    {
        "id": "region_rear_body",
        "label": "Rear Body",
        "zone_keys": ["rear_body", "trunk", "liftgate", "tail", "rear_panel"],
        "shape": "rect",
        "x": 650, "y": 78, "width": 130, "height": 130,
        "rx": 4,
        "cx": 714, "cy": 143,
    },
    {
        "id": "region_floor",
        "label": "Floor",
        "zone_keys": ["floor", "floor_panel", "underbody", "floor_cross"],
        "shape": "rect",
        "x": 198, "y": 240, "width": 448, "height": 36,
        "rx": 3,
        "cx": 422, "cy": 259,
    },
    {
        "id": "region_front_wheelhouse",
        "label": "Front Wheelhouse",
        "zone_keys": ["front_wheelhouse", "wheelhouse_front", "wheel_arch_front", "front_wheel_arch"],
        "shape": "rect",
        "x": 72, "y": 208, "width": 120, "height": 68,
        "rx": 30,
        "cx": 132, "cy": 244,
    },
    {
        "id": "region_rear_wheelhouse",
        "label": "Rear Wheelhouse",
        "zone_keys": ["rear_wheelhouse", "wheelhouse_rear", "wheel_arch_rear", "rear_wheel_arch"],
        "shape": "rect",
        "x": 648, "y": 208, "width": 120, "height": 68,
        "rx": 30,
        "cx": 708, "cy": 244,
    },
    {
        "id": "region_a_pillar",
        "label": "A-Pillar",
        "zone_keys": ["a_pillar", "a-pillar", "windshield_pillar"],
        "shape": "rect",
        "x": 170, "y": 38, "width": 32, "height": 170,
        "rx": 3,
        "cx": 186, "cy": 123,
    },
    {
        "id": "region_b_pillar",
        "label": "B-Pillar",
        "zone_keys": ["b_pillar", "b-pillar", "center_pillar"],
        "shape": "rect",
        "x": 354, "y": 38, "width": 14, "height": 200,
        "rx": 2,
        "cx": 361, "cy": 138,
    },
    {
        "id": "region_c_pillar",
        "label": "C-Pillar",
        "zone_keys": ["c_pillar", "c-pillar", "rear_pillar"],
        "shape": "rect",
        "x": 490, "y": 38, "width": 14, "height": 170,
        "rx": 2,
        "cx": 497, "cy": 123,
    },
]

# Zone status → CSS color token (dark mode)
ZONE_STATUS_COLORS: dict[str, dict] = {
    "inactive":  {"fill": "#2a2d3a", "stroke": "#3d4155", "label": "Not Involved"},
    "pending":   {"fill": "#1a3a5c", "stroke": "#2d6aa0", "label": "Planned"},
    "active":    {"fill": "#3a3000", "stroke": "#c8a800", "label": "Active"},
    "complete":  {"fill": "#0d2e1a", "stroke": "#27a85a", "label": "Complete"},
    "blocked":   {"fill": "#3a0d0d", "stroke": "#cc3333", "label": "Blocked"},
}

# Action status → color used in inspector badges
ACTION_STATUS_COLORS: dict[str, str] = {
    "pending":        "#6b7280",
    "in_progress":    "#c8a800",
    "complete":       "#27a85a",
    "blocked":        "#cc3333",
    "not_applicable": "#4b5563",
    "needs_review":   "#7c3aed",
}

# QA gate status → color
QA_STATUS_COLORS: dict[str, str] = {
    "open":            "#cc3333",
    "in_review":       "#c8a800",
    "passed":          "#27a85a",
    "failed":          "#cc3333",
    "not_applicable":  "#4b5563",
}

# Phase status → color
PHASE_STATUS_COLORS: dict[str, str] = {
    "not_started":     "#6b7280",
    "in_progress":     "#c8a800",
    "complete":        "#27a85a",
    "blocked":         "#cc3333",
    "ready_for_review": "#7c3aed",
    "not_applicable":  "#4b5563",
}
