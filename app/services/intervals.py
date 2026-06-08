"""
Intervals.icu API proxy service.

Provides two things:
1. A generic proxy — forward any request to the Intervals.icu API with auth.
2. A wellness PUT helper — applies unit conversions (lbs->kg, hours->sleepSecs)
   before proxying, so callers always work in conventional units.

Auth: HTTP Basic Auth, username="API_KEY", password=your API key.
Base URL: https://intervals.icu/api/v1
"""

import json
import logging
import httpx
from datetime import date
from typing import Any

from app.config import INTERVALS_API_KEY, INTERVALS_ATHLETE_ID, INTERVALS_BASE_URL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _client() -> httpx.Client:
    return httpx.Client(
        base_url=INTERVALS_BASE_URL,
        auth=("API_KEY", INTERVALS_API_KEY),
        headers={"Content-Type": "application/json"},
        timeout=10.0,
    )


def _athlete_path(path: str) -> str:
    return f"/athlete/{INTERVALS_ATHLETE_ID}{path}"


# ---------------------------------------------------------------------------
# Generic proxy
# ---------------------------------------------------------------------------

def _do_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """
    Low-level request helper — sends the request to the Intervals.icu API
    using the path exactly as given (no prefix expansion).
    """
    logger.info("intervals %s %s | params=%s | body=%s", method, path, params, json.dumps(body) if body else None)

    with _client() as c:
        r = c.request(method, path, params=params, json=body)
        if r.is_error:
            logger.error(
                "intervals %s %s FAILED | status=%s | response=%s",
                method, path, r.status_code, r.text
            )
        else:
            logger.info("intervals %s %s OK | status=%s", method, path, r.status_code)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        return r.json()


def request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """
    Forward any request to the Intervals.icu API (athlete-scoped).

    Shorthand paths that omit the /athlete/{id} prefix are expanded
    automatically.
    """
    if not path.startswith("/athlete/"):
        path = _athlete_path(path)
    return _do_request(method, path, params=params, body=body)


def activity_request(
    method: str,
    activity_id: str,
    suffix: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """
    Forward a request to an activity-scoped Intervals.icu endpoint.

    Path: /activity/{activity_id}/{suffix}
    No athlete prefix is prepended.
    """
    path = f"/activity/{activity_id}/{suffix}"
    return _do_request(method, path, params=params)


# ---------------------------------------------------------------------------
# Wellness unit conversion helpers
# ---------------------------------------------------------------------------

def _lbs_to_kg(lbs: float) -> float:
    return round(lbs * 0.453592, 2)


def _hours_to_secs(hours: float) -> int:
    return int(hours * 3600)


def build_wellness_payload(fields: dict) -> dict:
    """
    Convert a caller-friendly wellness dict (conventional units, snake_case)
    into an Intervals.icu Wellness schema payload (native units, camelCase).

    Only fields present in the input are included in the output —
    PUT is non-destructive so omitted fields are never overwritten.

    Unit conversions applied:
        weight_lbs      -> weight (kg)
        sleep_hours     -> sleepSecs (seconds)

    All other fields are renamed from snake_case to the Intervals.icu
    camelCase field name and passed through unchanged.
    """
    FIELD_MAP = {
        # Nutrition
        "calories":         "kcalConsumed",
        "protein_g":        "protein",
        "carbs_g":          "carbohydrates",
        "fat_g":            "fatTotal",
        # Sleep
        "sleep_score":      "sleepScore",
        "sleep_quality":    "sleepQuality",
        "avg_sleeping_hr":  "avgSleepingHR",
        # Heart & vitals
        "resting_hr":       "restingHR",
        "hrv":              "hrv",
        "hrv_sdnn":         "hrvSDNN",
        "spO2":             "spO2",
        "systolic":         "systolic",
        "diastolic":        "diastolic",
        "respiration":      "respiration",
        "baevsky_si":       "baevskySI",
        # Body composition
        "body_fat":         "bodyFat",
        "abdomen":          "abdomen",
        # Metabolic / lab
        "blood_glucose":    "bloodGlucose",
        "lactate":          "lactate",
        "vo2max":           "vo2max",
        # Subjective scores
        "fatigue":          "fatigue",
        "soreness":         "soreness",
        "mood":             "mood",
        "motivation":       "motivation",
        "stress":           "stress",
        "injury":           "injury",
        "readiness":        "readiness",
        # Hydration
        "hydration":        "hydration",
        "hydration_volume": "hydrationVolume",
        # Activity
        "steps":            "steps",
        # Free text
        "comments":         "comments",
    }

    payload = {}

    # Unit conversions
    if "weight_lbs" in fields and fields["weight_lbs"] is not None:
        payload["weight"] = _lbs_to_kg(fields["weight_lbs"])
    if "sleep_hours" in fields and fields["sleep_hours"] is not None:
        payload["sleepSecs"] = _hours_to_secs(fields["sleep_hours"])

    # Renamed passthrough fields
    for our_name, intervals_name in FIELD_MAP.items():
        if our_name in fields and fields[our_name] is not None:
            payload[intervals_name] = fields[our_name]

    return payload


def put_wellness(day: date, fields: dict) -> dict:
    """
    PUT /athlete/{id}/wellness/{date}

    Accepts fields in caller-friendly format (lbs, hours, snake_case),
    converts to Intervals.icu schema, then proxies.
    """
    payload = build_wellness_payload(fields)
    payload["id"] = day.isoformat()

    if not payload:
        raise ValueError("No valid fields provided — nothing to write.")

    logger.info("intervals put_wellness | date=%s | payload=%s", day.isoformat(), json.dumps(payload))
    return request("PUT", f"/wellness/{day.isoformat()}", body=payload)
