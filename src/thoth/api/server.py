"""Servidor FastAPI: dashboard web + REST de controle + telemetria.

Dois modos:
  - Unificado (`python -m thoth`): app.py popula o estado (mão + agentes) e sobe
    este servidor junto; aqui o lifespan NÃO gerencia a mão (managed_externally).
  - Standalone (`uvicorn thoth.api.server:app`): útil nas Fases 1–2; o lifespan
    conecta a mão sozinho para testar gestos pela web sem os agentes.

Rotas: `/` (dashboard), `/video` (MJPEG), `/ws` (telemetria), `/command`,
`/estop`, `/health`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from thoth.actuation.serial_client import HandLink
from thoth.api.routes import control, health, telemetry
from thoth.core.config import get_settings
from thoth.core.logging import setup_logging
from thoth.core.state import get_state

log = logging.getLogger("thoth.api")

STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    state = get_state()

    own_hand = False
    if not state.managed_externally and state.hand is None:
        # modo standalone: conecta a mão aqui
        hand = HandLink(
            port=settings.serial_port,
            baud=settings.serial_baud,
            heartbeat_period=settings.heartbeat_period,
        )
        try:
            await asyncio.wait_for(hand.connect(), timeout=8.0)
            state.hand = hand
            own_hand = True
        except Exception as exc:  # noqa: BLE001
            log.warning("Mão não conectada na API (%s).", exc)

    # Loop de espelhamento da mão (câmera -> servos), iniciado em background.
    mirror_task = None
    try:
        from thoth.perception.vision.mirror import mirror_loop

        mirror_task = asyncio.create_task(mirror_loop(settings), name="mirror")
    except Exception as exc:  # noqa: BLE001
        log.warning("Espelho indisponível (%s).", exc)

    try:
        yield
    finally:
        if mirror_task is not None:
            mirror_task.cancel()
        if own_hand and state.hand is not None:
            try:
                await state.hand.stop()
            except Exception:  # noqa: BLE001
                pass
            await state.hand.close()
            state.hand = None


app = FastAPI(title="Mendes API", version="0.1.0", lifespan=lifespan)

# Rotas de API ANTES de qualquer montagem em "/".
app.include_router(health.router)
app.include_router(control.router)
app.include_router(telemetry.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    """Serve o dashboard de controle."""
    return FileResponse(str(STATIC_DIR / "index.html"))
