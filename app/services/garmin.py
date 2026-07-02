"""
Garmin Connect service wrapper using python-garminconnect 0.3.x.

Auth: username/password with session token cached to disk after first MFA login.
Session token path: /data/garmin_tokens  (map this volume in Unraid)

login(tokenstore=path) handles both loading cached tokens and saving new ones
after a fresh login -- the correct approach in garminconnect 0.3.x.

WARNING: This uses an unofficial reverse-engineered API. Garmin may break it
at any time, and MFA enforcement may require periodic re-authentication via:
    docker exec -it <container> python -m app.services.garmin --reauth

Write support summary:
    Weight          OK  add_weigh_in() -- reliable
    Body comp       OK  via .fit file upload -- reliable
    Workouts        NOT IMPLEMENTED -- no schedule/create function exists
    Nutrition       NOT SUPPORTED -- Garmin's nutrition API is food-database-
                        based, not macro-total-based. Use Intervals.icu
                        wellness instead.
    Activity upload NOT SUPPORTED -- removed; no consumer for it.
"""

import logging
from datetime import date, datetime
from typing import Optional
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

from app.config import GARMIN_EMAIL, GARMIN_PASSWORD

logger = logging.getLogger(__name__)

# Token directory — map /data to persistent host storage in Unraid
SESSION_PATH = Path("/data/garmin_tokens")


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def _get_client() -> Garmin:
    """
    Return an authenticated Garmin client.

    login(tokenstore=path) handles both loading cached tokens and saving
    new ones after a fresh login -- correct API in garminconnect 0.3.x.
    MFA is handled interactively on first login.
    """
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD)

    try:
        client.login(tokenstore=str(SESSION_PATH))
        logger.info("Garmin: authenticated (token path: %s)", SESSION_PATH)
    except GarminConnectAuthenticationError as e:
        raise RuntimeError(
            f"Garmin authentication failed: {e}. "
            "Run `docker exec -it <container> python -m app.services.garmin --reauth` "
            "to complete MFA interactively."
        )

    return client


# ---------------------------------------------------------------------------
# Weight & Body Composition  <- primary write targets
# ---------------------------------------------------------------------------

def add_weigh_in(weight_kg: float, timestamp: Optional[datetime] = None) -> dict:
    """
    Log a weigh-in to Garmin Connect.

    Args:
        weight_kg:  Weight in kilograms.
        timestamp:  Datetime of the weigh-in. Always pass explicitly to avoid
                    UTC/local ambiguity -- do not rely on the default.

    Returns:
        Garmin API response dict.
    """
    client = _get_client()
    ts = timestamp.isoformat() if timestamp else ""
    result = client.add_weigh_in(weight=weight_kg, unitKey="kg", timestamp=ts)
    logger.info("Garmin: logged weigh-in %.1fkg at %s", weight_kg, ts or "now")
    return result or {}


def add_body_composition(
    timestamp: datetime,
    weight_kg: float,
    percent_fat: Optional[float] = None,
    percent_hydration: Optional[float] = None,
    visceral_fat_mass: Optional[float] = None,
    bone_mass: Optional[float] = None,
    muscle_mass: Optional[float] = None,
    bmi: Optional[float] = None,
) -> dict:
    """
    Upload a full body composition record via .fit file.

    Weight is required; all other fields are optional. Values not provided
    are omitted from the .fit record.
    """
    client = _get_client()
    result = client.add_body_composition(
        timestamp=timestamp,
        weight=weight_kg,
        percent_fat=percent_fat,
        percent_hydration=percent_hydration,
        visceral_fat_mass=visceral_fat_mass,
        bone_mass=bone_mass,
        muscle_mass=muscle_mass,
        bmi=bmi,
    )
    logger.info("Garmin: uploaded body composition for %s", timestamp.date())
    return result or {}


def get_weigh_ins(start_date: date, end_date: date) -> dict:
    """GET weigh-in history for a date range."""
    client = _get_client()
    return client.get_weigh_ins(
        startdate=start_date.isoformat(),
        enddate=end_date.isoformat(),
    ) or {}


def delete_weigh_in(weigh_in_id: str) -> None:
    """Delete a specific weigh-in record by ID."""
    client = _get_client()
    client.delete_weigh_in(weigh_in_id)
    logger.info("Garmin: deleted weigh-in %s", weigh_in_id)


# ---------------------------------------------------------------------------
# Daily health & activity (read)
# ---------------------------------------------------------------------------

def get_stats(log_date: date) -> dict:
    """GET daily stats summary (steps, calories, HR, stress, etc.)."""
    client = _get_client()
    return client.get_stats(cdate=log_date.isoformat()) or {}


def get_body_composition(log_date: date) -> dict:
    """GET body composition data for a date."""
    client = _get_client()
    d = log_date.isoformat()
    return client.get_body_composition(startdate=d, enddate=d) or {}


def get_heart_rates(log_date: date) -> dict:
    """GET heart rate data for a date."""
    client = _get_client()
    return client.get_heart_rates(cdate=log_date.isoformat()) or {}


def get_sleep_data(log_date: date) -> dict:
    """GET sleep data for a date."""
    client = _get_client()
    return client.get_sleep_data(cdate=log_date.isoformat()) or {}


def get_steps_data(log_date: date) -> dict:
    """GET steps data for a date."""
    client = _get_client()
    return client.get_steps_data(cdate=log_date.isoformat()) or {}


# ---------------------------------------------------------------------------
# User & profile (read)
# ---------------------------------------------------------------------------

def get_full_name() -> str:
    """GET the authenticated user's display name."""
    client = _get_client()
    return client.get_full_name() or ""


def get_unit_system() -> dict:
    """GET the user's preferred unit system."""
    client = _get_client()
    return client.get_unit_system() or {}


# ---------------------------------------------------------------------------
# Activities (read/write)
# ---------------------------------------------------------------------------

def get_activities(start: int = 0, limit: int = 20) -> list:
    """GET recent activities."""
    client = _get_client()
    return client.get_activities(start, limit) or []


def get_activity(activity_id: str) -> dict:
    """GET a single activity by ID."""
    client = _get_client()
    return client.get_activity(activity_id) or {}


# ---------------------------------------------------------------------------
# Interactive re-auth entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--reauth" in sys.argv:
        print("Starting interactive Garmin re-authentication...")
        # Remove cached tokens to force fresh login
        import shutil
        if SESSION_PATH.exists():
            shutil.rmtree(str(SESSION_PATH), ignore_errors=True)
            SESSION_PATH.unlink(missing_ok=True)
        client = _get_client()
        print(f"Success -- session saved to {SESSION_PATH}")
    else:
        print("Usage: python -m app.services.garmin --reauth")
