"""
API key authentication dependency.
All routers depend on this — every request must include:
    X-API-Key: <FITNESS_API_KEY>
"""

from fastapi import Header, HTTPException, status
from app.config import API_KEY


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
