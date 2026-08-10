"""Servidor web do Jokenpô Robótico + entry point.

Serve o placar (SPA), o vídeo anotado da câmera (MJPEG) e a API do jogo. Cada
rodada roda o workflow Agno (``fluxo``), que detecta o gesto, sorteia a jogada
do robô, move a mão HACKberry, julga e narra por voz (Claude/Anthropic + TTS).

A mão e a câmera são iniciadas no ``lifespan`` (via ``game.services``).

Rodar:  python orquestrador.py   (http://127.0.0.1:7777)
"""
from __future__ import annotations

import base64
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import Body, FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# `game` ajusta o sys.path para achar o pacote `thoth` do projeto pai.
from game.services import get_services
from game.state import get_state
from workflow_jokenpo_robotico import fluxo

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("jokenpo.web")

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    svc = get_services()
    await anyio.to_thread.run_sync(svc.startup)
    st = get_state()
    log.info("Jokenpô pronto — braço=%s, câmera=%s", st.arm_connected, st.camera_on)
    try:
        yield
    finally:
        await anyio.to_thread.run_sync(svc.shutdown)


app = FastAPI(title="Jokenpô Robótico", version="1.0.0", lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/estado")
async def estado() -> dict:
    return get_state().snapshot()


@app.post("/api/jogar")
async def jogar(payload: dict | None = Body(default=None)) -> JSONResponse:
    """Roda uma rodada (workflow Agno) e devolve o resultado completo."""
    add: dict = {"user_id": "web"}
    gesto = (payload or {}).get("gesto")
    if gesto:  # jogada manual (útil para testar sem câmera)
        add["gesto_manual"] = gesto
    res = await fluxo.arun(input="jogar", additional_data=add,
                           session_id="web", user_id="web")
    content = getattr(res, "content", None)
    if not isinstance(content, dict):
        content = {"erro": "resultado_inesperado"}
    return JSONResponse(content)


@app.post("/api/saudar")
async def saudar() -> dict:
    svc = get_services()
    texto = await svc.narrator.saudar(get_state().placar())
    out: dict = {"narracao": texto, "audio_b64": None}
    res = await anyio.to_thread.run_sync(svc.narrator.sintetizar, texto)
    if res:
        mime, data = res
        out["audio_b64"] = base64.b64encode(data).decode("ascii")
        out["audio_mime"] = mime
    return out


@app.post("/api/reset")
async def reset() -> dict:
    get_state().reset()
    return get_state().snapshot()


@app.post("/api/estop")
async def estop() -> dict:
    """Parada de emergência: abre a mão em posição segura."""
    ok = await anyio.to_thread.run_sync(get_services().arm.parar)
    return {"ok": ok}


def _mjpeg():
    """Gerador MJPEG do último frame anotado (~15 fps)."""
    while True:
        buf = get_state().get_frame_jpeg()
        if buf:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n")
        time.sleep(1 / 15)


@app.get("/video")
async def video() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7777, log_level="info")
