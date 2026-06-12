"""Modelos Pydantic de request/response da API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from thoth.safety.limits import VALID_GESTURES


class CommandRequest(BaseModel):
    gesto: str = Field(..., description=f"Um de: {sorted(VALID_GESTURES)}")


class CommandResponse(BaseModel):
    ok: bool
    detalhe: str


class HealthResponse(BaseModel):
    status: str
    hand_connected: bool
    version: str
