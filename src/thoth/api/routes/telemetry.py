"""Telemetria da web: stream de vídeo (MJPEG) e websocket de status/eventos."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from thoth.core.state import get_state

router = APIRouter(tags=["telemetry"])

_BOUNDARY = "frame"


async def _mjpeg_generator():
    """Gera um stream MJPEG (multipart) a partir do último frame anotado."""
    state = get_state()
    while True:
        jpeg = state.get_frame()
        if jpeg:
            yield (
                b"--" + _BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
        await asyncio.sleep(1 / 15)  # ~15 FPS no navegador


@router.get("/video")
async def video() -> StreamingResponse:
    """Stream de vídeo da visão computacional (com anotações)."""
    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Empurra o snapshot do estado (status da mão, transcrição, eventos) ~3 Hz."""
    await websocket.accept()
    state = get_state()
    try:
        while True:
            await websocket.send_json(state.snapshot())
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        return
