"""Loop de espelhamento: câmera -> rastreia a mão -> move os servos do braço.

Quando ``state.mirror_enabled`` está True: captura a webcam, calcula a flexão de
cada dedo (HandTracker) e envia os ângulos para a mão (HandLink), além de publicar
o frame anotado para o stream de vídeo. Desliga a câmera quando o modo é desativado.
"""
from __future__ import annotations

import asyncio
import logging

import cv2

from thoth.core.config import Settings
from thoth.core.state import get_state
from thoth.safety.limits import clamp_all

log = logging.getLogger("thoth.mirror")

_SEND_PERIOD = 0.06   # ~16 Hz máx de comandos ao braço
_DEADBAND = 3         # só envia se algum ângulo mudar >= 3°

# Faixa de saída por dedo no espelho (lógico).
_RANGE = {
    "thumb": (15, 165),
    "index": (15, 165),
    "other": (15, 165),
}


def _to_angle(f: float, lo: int, hi: int) -> int:
    """Flexão 0..1 (0=aberto,1=fechado) -> ângulo lógico na faixa [lo, hi]."""
    return int(round(lo + f * (hi - lo)))


async def mirror_loop(settings: Settings) -> None:
    """Roda continuamente; só age quando state.mirror_enabled é True."""
    state = get_state()
    cam = None
    tracker = None
    last_sent = 0.0
    last_angles: tuple[int, int, int] | None = None
    loop = asyncio.get_event_loop()

    def _release():
        nonlocal cam, tracker
        if cam is not None:
            cam.stop(); cam = None
        if tracker is not None:
            tracker.close(); tracker = None
        state.mirror_hand_seen = False
        state.mirror_flex = None

    try:
        while True:
            if not state.mirror_enabled:
                if cam is not None:
                    _release()
                await asyncio.sleep(0.1)
                continue

            if cam is None:
                try:
                    from thoth.core.config import PROJECT_ROOT
                    from thoth.perception.vision.camera import WebcamStream
                    from thoth.perception.vision.hand_tracking import HandTracker

                    model = PROJECT_ROOT / "models" / "mediapipe" / "hand_landmarker.task"
                    cam = WebcamStream(
                        src=settings.camera_index,
                        width=settings.camera_width,
                        height=settings.camera_height,
                    ).start()
                    tracker = HandTracker(model_path=model)
                    log.info("espelho ligado (câmera %s)", settings.camera_index)
                    state.push_event("espelho", {"status": "ligado"})
                except Exception as exc:  # noqa: BLE001
                    log.warning("não consegui abrir câmera/rastreador: %s", exc)
                    state.mirror_enabled = False
                    state.push_event("espelho_erro", {"erro": str(exc)})
                    await asyncio.sleep(0.3)
                    continue

            frame = cam.read()
            if frame is None:
                await asyncio.sleep(0.02)
                continue

            annotated, flex = await asyncio.to_thread(tracker.process, frame)
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                state.set_frame(buf.tobytes())
            state.fps = cam.fps_measured
            state.mirror_hand_seen = flex is not None

            if flex is not None:
                thumb_f, index_f, other_f = flex
                state.mirror_flex = (
                    round(thumb_f * 100), round(index_f * 100), round(other_f * 100)
                )
                ang = clamp_all(
                    _to_angle(thumb_f, *_RANGE["thumb"]),
                    _to_angle(index_f, *_RANGE["index"]),
                    _to_angle(other_f, *_RANGE["other"]),
                )
                hand = state.hand
                now = loop.time()
                changed = last_angles is None or any(
                    abs(a - b) >= _DEADBAND for a, b in zip(ang, last_angles)
                )
                if hand is not None and changed and (now - last_sent) > _SEND_PERIOD:
                    try:
                        await hand.set_angles(ang[0], ang[1], ang[2])  # thumb, index, other
                        last_sent = now
                        last_angles = ang
                    except Exception:  # noqa: BLE001
                        pass
            await asyncio.sleep(0.02)
    except asyncio.CancelledError:
        raise
    finally:
        _release()
