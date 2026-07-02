"""
Intervals.icu router.

Pure passthrough to the Intervals.icu API. No custom Pydantic models, no
field renaming, no unit conversion. Callers send the exact field names and
native units defined by the Intervals.icu OpenAPI spec
(https://intervals.icu/api/v1/docs) — e.g. wellness bodies use
`kcalConsumed`, `carbohydrates`, `protein`, `fatTotal`, `weight` (kg),
`sleepSecs` (seconds).

All endpoints require the X-API-Key header matching FITNESS_API_KEY.
Dates are always passed explicitly by the caller to avoid UTC/ET ambiguity.
"""

from datetime import date
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services import intervals as svc
from app.auth import require_api_key

router = APIRouter(
    prefix="/intervals",
    tags=["intervals"],
    dependencies=[Depends(require_api_key)],
)


# ---------------------------------------------------------------------------
# Error handler — pass upstream errors through with real status codes
# ---------------------------------------------------------------------------

def _proxy_error(e: Exception) -> HTTPException:
    if isinstance(e, httpx.HTTPStatusError):
        return HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    return HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Wellness endpoints — raw passthrough
# ---------------------------------------------------------------------------

@router.put("/wellness/{day}")
async def put_wellness(day: date, request: Request):
    """
    Create or update a wellness record for a specific date.

    Body must match the Intervals.icu Wellness schema exactly (e.g.
    kcalConsumed, carbohydrates, protein, fatTotal, weight in kg,
    sleepSecs in seconds). Forwarded as-is — no field renaming or unit
    conversion. PUT is non-destructive for omitted fields.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="No fields provided.")
    try:
        return svc.request("PUT", f"/wellness/{day.isoformat()}", body=body)
    except Exception as e:
        raise _proxy_error(e)


@router.get("/wellness/{day}")
def get_wellness_day(day: date):
    """Get a single day's wellness record."""
    try:
        return svc.request("GET", f"/wellness/{day.isoformat()}")
    except Exception as e:
        raise _proxy_error(e)


@router.get("/wellness")
def get_wellness(oldest: Optional[date] = None, newest: Optional[date] = None):
    """Get wellness records for a date range."""
    params = {}
    if oldest:
        params["oldest"] = oldest.isoformat()
    if newest:
        params["newest"] = newest.isoformat()
    try:
        return svc.request("GET", "/wellness", params=params)
    except Exception as e:
        raise _proxy_error(e)


# ---------------------------------------------------------------------------
# Activity-scoped endpoints — NOT athlete-prefixed
# ---------------------------------------------------------------------------

@router.get("/activity/{activity_id}/streams")
def get_activity_streams(activity_id: str, types: Optional[str] = None):
    """
    Get time-series sensor streams for an activity.

    Proxies GET /api/v1/activity/{id}/streams to Intervals.icu.
    Pass `types` as a comma-separated list of stream names, e.g.
    watts,heart_rate,cadence.
    """
    params = {}
    if types:
        params["types"] = types
    try:
        return svc.activity_request("GET", activity_id, "streams", params=params or None)
    except Exception as e:
        raise _proxy_error(e)


@router.get("/activity/{activity_id}/weather")
def get_activity_weather(
    activity_id: str,
    start_index: Optional[int] = None,
    end_index: Optional[int] = None,
):
    """
    Get weather summary for an activity.

    Proxies GET /api/v1/activity/{id}/weather-summary to Intervals.icu.
    Returns ambient temperature, wind speed, humidity, and headwind/tailwind %.
    """
    params = {}
    if start_index is not None:
        params["start_index"] = start_index
    if end_index is not None:
        params["end_index"] = end_index
    try:
        return svc.activity_request("GET", activity_id, "weather-summary", params=params or None)
    except Exception as e:
        raise _proxy_error(e)


# ---------------------------------------------------------------------------
# Generic proxy — all other Intervals.icu endpoints
#
# Accepts any path under /intervals/proxy/{path} and forwards it to
# the Intervals.icu API with athlete ID prepended automatically.
#
# Examples:
#   GET  /intervals/proxy/activities?oldest=2026-04-01
#   GET  /intervals/proxy/activities/i123456789
#   POST /intervals/proxy/events   (body in request)
#   PUT  /intervals/proxy/events/987654
#   DELETE /intervals/proxy/events/987654
#   GET  /intervals/proxy/sport-settings/Ride
# ---------------------------------------------------------------------------

@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    """
    Generic proxy to any Intervals.icu API endpoint.
    The athlete ID is prepended automatically — pass only the path
    after /athlete/{id}/, e.g. 'activities', 'events/123', 'sport-settings/Ride'.
    Query parameters and request body are forwarded as-is.
    """
    params = dict(request.query_params)
    body = None
    if request.method in ("POST", "PUT"):
        try:
            body = await request.json()
        except Exception:
            body = None
    try:
        result = svc.request(request.method, f"/{path}", params=params, body=body)
        if result is None:
            return JSONResponse(status_code=204, content=None)
        return result
    except Exception as e:
        raise _proxy_error(e)
