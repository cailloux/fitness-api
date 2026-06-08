"""
Garmin Connect router.

All endpoints require the X-API-Key header matching FITNESS_API_KEY.
Dates and timestamps are always passed explicitly — nothing defaults to
server-side "now", avoiding UTC/local timezone ambiguity.

Write support is narrow by design — Garmin's unofficial API is fragile.
Confirmed reliable writes:
    - Weight via add_weigh_in()
    - Body composition via set_body_composition() (.fit file upload)
    - Activity file upload
    - Structured workout creation and scheduling

Nutrition write is not implemented — see garmin.py service for rationale.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services import garmin as svc
from app.auth import require_api_key

router = APIRouter(
    prefix="/garmin",
    tags=["garmin"],
    dependencies=[Depends(require_api_key)],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class WeighIn(BaseModel):
    weight_lbs: float = Field(..., description="Weight in lbs — converted to kg before write")
    timestamp: Optional[datetime] = Field(
        None,
        description=(
            "Datetime of the weigh-in in local time (e.g. 2024-01-15T07:00:00). "
            "Always pass this explicitly — do not omit, as the server clock is UTC "
            "and will write to the wrong time without it."
        ),
    )


class BodyComposition(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Datetime of measurement in local time (e.g. 2024-01-15T07:00:00)",
    )
    weight_lbs: float = Field(..., description="Weight in lbs — converted to kg")
    percent_fat: Optional[float] = None
    percent_hydration: Optional[float] = None
    visceral_fat_mass: Optional[float] = None
    bone_mass: Optional[float] = None
    muscle_mass: Optional[float] = None
    bmi: Optional[float] = None


class DateParam(BaseModel):
    log_date: Optional[date] = Field(
        None,
        description="Date in YYYY-MM-DD. Always pass explicitly to avoid UTC/local ambiguity.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lbs_to_kg(lbs: float) -> float:
    return round(lbs * 0.453592, 2)


# ---------------------------------------------------------------------------
# Weight & Body Composition  ← primary write targets
# ---------------------------------------------------------------------------

@router.post("/weight")
def add_weigh_in(body: WeighIn):
    """
    Log a weigh-in to Garmin Connect.
    Weight in lbs is converted to kg before write.
    Always pass timestamp in local time to avoid writing to the wrong day.
    """
    weight_kg = _lbs_to_kg(body.weight_lbs)
    try:
        return svc.add_weigh_in(weight_kg=weight_kg, timestamp=body.timestamp)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/body-composition")
def add_body_composition(body: BodyComposition):
    """
    Upload a full body composition record via .fit file.
    Weight required; all other fields optional.
    """
    weight_kg = _lbs_to_kg(body.weight_lbs)
    try:
        return svc.add_body_composition(
            timestamp=body.timestamp,
            weight_kg=weight_kg,
            percent_fat=body.percent_fat,
            percent_hydration=body.percent_hydration,
            visceral_fat_mass=body.visceral_fat_mass,
            bone_mass=body.bone_mass,
            muscle_mass=body.muscle_mass,
            bmi=body.bmi,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/weight")
def get_weigh_ins(start_date: date, end_date: date):
    """Get weigh-in history for a date range."""
    try:
        return svc.get_weigh_ins(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/weight/{weigh_in_id}", status_code=204)
def delete_weigh_in(weigh_in_id: str):
    """Delete a specific weigh-in by ID."""
    try:
        svc.delete_weigh_in(weigh_in_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/body-composition")
def get_body_composition(log_date: date):
    """Get body composition data for a date."""
    try:
        return svc.get_body_composition(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Nutrition  ⚠️  read-only — write not implemented
# ---------------------------------------------------------------------------

@router.get("/nutrition")
def get_nutrition(log_date: date):
    """Get nutrition summary for a date (read-only)."""
    try:
        return svc.get_nutrition_day(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/nutrition")
def log_nutrition():
    """
    ⚠️  Not implemented.
    Garmin's nutrition API is food-database-based; raw macro logging is not
    supported. Use PUT /intervals/wellness/{date} for macro logging instead.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Garmin nutrition write is not implemented. "
            "Use PUT /intervals/wellness/{date} to log calories and macros."
        ),
    )


# ---------------------------------------------------------------------------
# Daily health (read)
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(log_date: date):
    """Get daily stats (steps, calories burned, HR, stress, etc.)."""
    try:
        return svc.get_stats(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/heart-rate")
def get_heart_rates(log_date: date):
    """Get heart rate data for a date."""
    try:
        return svc.get_heart_rates(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/sleep")
def get_sleep(log_date: date):
    """Get sleep data for a date."""
    try:
        return svc.get_sleep_data(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/steps")
def get_steps(log_date: date):
    """Get steps data for a date."""
    try:
        return svc.get_steps_data(log_date=log_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# User & profile (read)
# ---------------------------------------------------------------------------

@router.get("/profile")
def get_profile():
    """Get the authenticated user's name and unit preferences."""
    try:
        return {
            "name": svc.get_full_name(),
            "units": svc.get_unit_system(),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Activities (read/write)
# ---------------------------------------------------------------------------

@router.get("/activities")
def get_activities(start: int = 0, limit: int = 20):
    """Get recent activities."""
    try:
        return svc.get_activities(start=start, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/activities/{activity_id}")
def get_activity(activity_id: str):
    """Get a single activity by ID."""
    try:
        return svc.get_activity(activity_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
