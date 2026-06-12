"""Liveness/readiness."""
from __future__ import annotations

from fastapi import APIRouter

from thoth import __version__
from thoth.api.schemas import HealthResponse
from thoth.core.state import get_state

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    hand = get_state().hand
    connected = bool(hand and hand._connected.is_set())
    return HealthResponse(status="ok", hand_connected=connected, version=__version__)
