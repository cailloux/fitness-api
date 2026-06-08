"""
Intervals.icu router.

The wellness endpoint handles unit conversion (lbs->kg, hours->sleepSecs)
via a typed Pydantic model before proxying. All other endpoints are thin
pass-throughs to the Intervals.icu API via the proxy service.

All endpoints require the X-API-Key header matching FITNESS_API_KEY.
Dates are always passed explicitly by the caller to avoid UTC/ET ambiguity.
"""

from datetime import date
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services import intervals as svc
from app.auth import require_api_key

router = APIRouter(
    prefix="/intervals",
    tags=["intervals"],
    dependencies=[Depends(require_api_key)],
)


# ---------------------------------------------------------------------------
# Wellness model — typed because we apply unit conversions here
# ---------------------------------------------------------------------------

class WellnessUpdate(BaseModel):
    """
    Wellness record for a single day.
    All fields optional — only provided fields are written.
    Intervals.icu PUT is non-destructive for omitted fields.

    Unit conversions applied by this API:
        weight_lbs  -> weight (kg)
        sleep_hours -> sleepSecs (seconds)

    All other fields map directly to Intervals.icu field names via build_wellness_payload().
    """
    # Weight
    weight_lbs: Optional[float] = Field(None, description="Weight in lbs — converted to kg")

    # Nutrition
    calories: Optional[int] = Field(None, description="Calories (kcal) -> kcalConsumed")
    protein_g: Optional[float] = Field(None, description="Protein (g) -> protein")
    carbs_g: Optional[float] = Field(None, description="Carbohydrates (g) -> carbohydrates")
    fat_g: Optional[float] = Field(None, description="Fat (g) -> fatTotal")

    # Sleep
    sleep_hours: Optional[float] = Field(None, description="Sleep duration in hours -> sleepSecs")
    sleep_score: Optional[float] = Field(None, description="Sleep score -> sleepScore")
    sleep_quality: Optional[int] = Field(None, description="Sleep quality 1-4 -> sleepQuality")
    avg_sleeping_hr: Optional[float] = Field(None, description="Avg sleeping HR -> avgSleepingHR")

    # Heart & vitals
    resting_hr: Optional[int] = Field(None, description="Resting HR (bpm) -> restingHR")
    hrv: Optional[float] = Field(None, description="HRV (ms) -> hrv")
    hrv_sdnn: Optional[float] = Field(None, description="HRV SDNN (ms) -> hrvSDNN")
    spO2: Optional[float] = Field(None, description="Blood oxygen % -> spO2")
    systolic: Optional[int] = Field(None, description="Systolic BP (mmHg) -> systolic")
    diastolic: Optional[int] = Field(None, description="Diastolic BP (mmHg) -> diastolic")
    respiration: Optional[float] = Field(None, description="Respiration rate -> respiration")
    baevsky_si: Optional[float] = Field(None, description="Baevsky stress index -> baevskySI")

    # Body composition
    body_fat: Optional[float] = Field(None, description="Body fat % -> bodyFat")
    abdomen: Optional[float] = Field(None, description="Abdomen measurement -> abdomen")

    # Metabolic / lab
    blood_glucose: Optional[float] = Field(None, description="Blood glucose -> bloodGlucose")
    lactate: Optional[float] = Field(None, description="Lactate -> lactate")
    vo2max: Optional[float] = Field(None, description="VO2max -> vo2max")

    # Subjective scores
    fatigue: Optional[int] = Field(None, ge=1, le=5, description="Fatigue 1-5")
    soreness: Optional[int] = Field(None, ge=1, le=5, description="Soreness 1-5")
    mood: Optional[int] = Field(None, ge=1, le=5, description="Mood 1-5")
    motivation: Optional[int] = Field(None, ge=1, le=5, description="Motivation 1-5")
    stress: Optional[int] = Field(None, ge=1, le=5, description="Stress 1-5")
    injury: Optional[int] = Field(None, description="Injury score -> injury")
    readiness: Optional[float] = Field(None, description="Readiness 0-100 -> readiness")

    # Hydration
    hydration: Optional[int] = Field(None, description="Hydration score -> hydration")
    hydration_volume: Optional[float] = Field(None, description="Hydration volume -> hydrationVolume")

    # Activity
    steps: Optional[int] = Field(None, description="Steps -> steps")

    # Free text
    comments: Optional[str] = Field(None, description="Free text -> comments")


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
# Wellness endpoints — typed, with unit conversion
# ---------------------------------------------------------------------------

@router.put("/wellness/{day}")
def put_wellness(day: date, body: WellnessUpdate):
    """
    Create or update a wellness record for a specific date.
    Weight in lbs is converted to kg. Sleep in hours converted to seconds.
    All other fields passed through after field name mapping.
    """
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided.")
    try:
        return svc.put_wellness(day, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
