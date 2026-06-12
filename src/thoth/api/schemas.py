"""Modelos Pydantic de request/response da API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from thoth.safety.limits import VALID_GESTURES


class CommandRequest(BaseModel):
    gesto: str = Field(..., description=f"Um de: {sorted(VALID_GESTURES)}")


class AnglesRequest(BaseModel):
    """Ângulos lógicos por dedo (o firmware aplica o clamp aos limites)."""
    thumb: int = Field(..., ge=0, le=180)
    index: int = Field(..., ge=0, le=180)
    other: int = Field(..., ge=0, le=180)


class MirrorRequest(BaseModel):
    """Liga/desliga o modo 'espelhar minha mão' (câmera -> servos)."""
    enabled: bool


class CommandResponse(BaseModel):
    ok: bool
    detalhe: str


class HealthResponse(BaseModel):
    status: str
    hand_connected: bool
    version: str
