"""
Internal FastAPI router for the RepairGraph golden-path demo experience.

Exposes GET /internal/demo — the recommended entry point for demonstrating
RepairGraph to MSO executives, OEM representatives, shop owners, and
strategic partners.

All business logic is delegated to existing modules. This router is pure
orchestration and HTML rendering.

Advisory: All outputs are advisory workflow intelligence derived from RepairGraph
procedure data. No repair certification or OEM compliance is implied.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from repairgraph.demo.demo_page import build_demo_page_html
from repairgraph.demo.orchestrator import build_full_demo_payload

router = APIRouter(prefix="/internal", tags=["demo"])

_ENDPOINT_ADVISORY = (
    "This endpoint is the RepairGraph golden-path demonstration. "
    "It is a local/internal demo endpoint and is not an authenticated "
    "production API surface. All outputs are advisory workflow intelligence."
)


@router.get(
    "/demo",
    summary="RepairGraph end-to-end golden-path demo",
    response_class=HTMLResponse,
)
def get_demo() -> HTMLResponse:
    """Return the self-contained RepairGraph demo experience.

    Renders a step-by-step guided workflow from OEM intake through repair
    intelligence visualization. Embeds all data as JSON — no external
    dependencies, no CDN, no frameworks.

    Steps:
      1. OEM Intake
      2. Packet Analysis
      3. Generate Repair Intelligence
      4. Interactive Topology Viewer
      5. Event Replay
      6. Repair Intelligence Summary
      7. Export
    """
    html_content = build_demo_page_html()
    return HTMLResponse(content=html_content, status_code=200)


@router.get(
    "/demo/payload",
    summary="RepairGraph demo orchestration payload (JSON)",
)
def get_demo_payload() -> dict[str, Any]:
    """Return the full demo orchestration payload as JSON.

    Combines intake classification results and complete workflow intelligence
    into a single serializable payload. Useful for debugging and integration.
    """
    payload = build_full_demo_payload()
    payload["endpoint_advisory"] = _ENDPOINT_ADVISORY
    return payload
