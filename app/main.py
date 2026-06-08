"""
Fitness API — main entrypoint.

Mounts:
    /intervals  — Intervals.icu API wrapper
    /garmin     — Garmin Connect wrapper

Auth: X-API-Key header required on all routes.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routers import intervals, garmin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fitness API",
    description="Personal fitness data API — Intervals.icu and Garmin Connect.",
    version="0.1.0",
    # Disable docs in production if desired; useful during development
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(intervals.router)
app.include_router(garmin.router)


@app.get("/health")
def health():
    """Liveness check — no auth required."""
    return JSONResponse({"status": "ok"})
