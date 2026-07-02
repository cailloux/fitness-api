"""
Intervals.icu API proxy service.

A generic proxy — forwards any request to the Intervals.icu API with auth.
No field renaming, no unit conversion, no custom models. Callers send
Intervals.icu's native field names and units directly
(see https://intervals.icu/api/v1/docs).

Auth: HTTP Basic Auth, username="API_KEY", password=your API key.
Base URL: https://intervals.icu/api/v1
"""

import json
import logging
import httpx
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


