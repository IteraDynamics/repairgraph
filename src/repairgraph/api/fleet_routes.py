"""
FastAPI router for the Fleet Summary — a shop-floor view across all jobs.

GET /internal/fleet      — fleet summary as JSON
GET /internal/fleet/ui   — self-contained HTML dashboard

Aggregates every job present in data/normalized/ into status buckets
(blocked / in_progress / not_started / ready / cancelled) so a manager can
see where attention is needed without opening each job's review individually.
Reuses the same state projection as /internal/review/progress — a job's
bucket reflects its actual recorded progress, not a static snapshot.

All outputs are advisory.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from repairgraph.state.fleet import build_fleet_summary

router = APIRouter(prefix="/internal", tags=["fleet"])


@router.get(
    "/fleet",
    summary="Fleet summary — all tracked jobs grouped by status",
)
def get_fleet() -> dict[str, Any]:
    """Return a summary of every job in data/normalized/, grouped by status.

    Each job's status is derived by replaying its recorded progress events
    (if any) over its initial state — the same projection /internal/review
    uses, so this view always matches what each job's review page shows.

    All outputs are advisory.
    """
    return build_fleet_summary()


@router.get(
    "/fleet/ui",
    summary="Fleet dashboard — self-contained HTML",
    response_class=HTMLResponse,
)
def get_fleet_ui() -> HTMLResponse:
    """Return the Fleet Summary dashboard as self-contained HTML.

    No CDN. No external JS. No frameworks. All outputs are advisory.
    """
    from repairgraph.review.fleet_page import build_fleet_page_html

    summary = build_fleet_summary()
    html = build_fleet_page_html(summary)
    return HTMLResponse(content=html, status_code=200)
