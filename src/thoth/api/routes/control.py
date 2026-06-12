"""Comandos manuais de movimento e parada de emergência (usados pelo dashboard)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from thoth.actuation import motion_primitives as motion
from thoth.api.schemas import AnglesRequest, CommandRequest, CommandResponse, MirrorRequest
from thoth.core.state import get_state
from thoth.safety.limits import VALID_GESTURES, clamp_all

router = APIRouter(tags=["control"])


@router.post("/mirror", response_model=CommandResponse)
async def mirror(req: MirrorRequest) -> CommandResponse:
    """Liga/desliga o espelhamento da mão (câmera -> braço)."""
    state = get_state()
    state.mirror_enabled = req.enabled
    state.push_event("espelho", {"ligado": req.enabled})
    return CommandResponse(ok=True, detalhe=f"espelho {'ligado' if req.enabled else 'desligado'}")


@router.post("/angles", response_model=CommandResponse)
async def angles(req: AnglesRequest) -> CommandResponse:
    """Controle por dedo: define os ângulos (polegar, indicador, três dedos)."""
    hand = get_state().hand
    if hand is None:
        raise HTTPException(status_code=503, detail="mão não conectada")
    t, i, o = clamp_all(req.thumb, req.index, req.other)  # clampa aos limites antes de enviar
    ack = await hand.set_angles(t, i, o)
    return CommandResponse(ok=True, detalhe=f"G:{t},{i},{o} ({ack})")


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
