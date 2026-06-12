"""Comandos manuais de movimento e parada de emergência (usados pelo dashboard)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from thoth.actuation import motion_primitives as motion
from thoth.api.schemas import CommandRequest, CommandResponse
from thoth.core.state import get_state
from thoth.safety.limits import VALID_GESTURES

router = APIRouter(tags=["control"])


@router.post("/command", response_model=CommandResponse)
async def command(req: CommandRequest) -> CommandResponse:
    hand = get_state().hand
    if hand is None:
        raise HTTPException(status_code=503, detail="mão não conectada")
    gesto = req.gesto.strip().lower()
    if gesto not in VALID_GESTURES:
        raise HTTPException(status_code=400, detail=f"gesto inválido; use {sorted(VALID_GESTURES)}")
    ack = await motion.GESTURES[gesto](hand)
    get_state().push_event("comando_web", {"gesto": gesto})
    return CommandResponse(ok=True, detalhe=f"gesto '{gesto}' executado (ACK={ack})")


@router.post("/estop", response_model=CommandResponse)
async def estop() -> CommandResponse:
    hand = get_state().hand
    if hand is None:
        raise HTTPException(status_code=503, detail="mão não conectada")
    ack = await hand.stop()
    get_state().push_event("estop_web", {})
    return CommandResponse(ok=True, detalhe=f"e-stop: mão aberta (ACK={ack})")
