"""Health check router (§5.8)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe for Docker / deployment. Always returns ok."""
    return {"status": "ok"}
