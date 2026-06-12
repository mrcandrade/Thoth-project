"""Pipeline de visão: captura, reconhece pessoas, ANOTA o frame e publica eventos.

- Publica ``PERSON_RECOGNIZED`` quando a identidade muda (debounce simples).
- Desenha caixas/nomes e grava o frame JPEG anotado no estado compartilhado
  (``AppState.latest_jpeg``), que alimenta o stream de vídeo da interface web.
- A inferência roda em thread (``asyncio.to_thread``) numa cadência menor que a
  captura, para não bloquear o event loop nem saturar a CPU.
"""
from __future__ import annotations

import asyncio
import logging

from thoth.core import events
from thoth.core.config import Settings
from thoth.core.event_bus import EventBus
from thoth.core.state import get_state

log = logging.getLogger("thoth.vision")


def _annotate(frame, detections):
    """Desenha bounding boxes e nomes no frame (in-place)."""
    import cv2

    for name, conf, box in detections:
        top, right, bottom, left = box  # formato do face_recognition
        cor = (0, 200, 0) if name != "Desconhecido" else (0, 0, 220)
        cv2.rectangle(frame, (left, top), (right, bottom), cor, 2)
        rotulo = name if name == "Desconhecido" else f"{name} {conf:.0%}"
        cv2.rectangle(frame, (left, bottom - 22), (right, bottom), cor, cv2.FILLED)
        cv2.putText(frame, rotulo, (left + 4, bottom - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return frame


async def vision_loop(bus: EventBus, settings: Settings, period: float = 0.15) -> None:
    """Loop de visão. Encerra de forma limpa quando a task é cancelada."""
    import cv2

    from thoth.perception.vision.camera import WebcamStream
    from thoth.perception.vision.face_recognizer import FaceRecognizer

    state = get_state()
    cam = WebcamStream(
        src=settings.camera_index,
        width=settings.camera_width,
        height=settings.camera_height,
    ).start()

    recognizer: FaceRecognizer | None = None
    try:
        recognizer = FaceRecognizer(
            gallery_path=settings.face_gallery_path,
            tolerance=settings.face_match_threshold,
        )
    except FileNotFoundError:
        log.warning(
            "Galeria facial não encontrada (%s). Rode `just enroll <nome>` primeiro. "
            "Seguindo só com vídeo, sem reconhecimento.",
            settings.face_gallery_path,
        )

    last_seen: str | None = None
    try:
        while True:
            frame = cam.read()
            if frame is not None:
                if recognizer is not None:
                    detections = await asyncio.to_thread(recognizer.identify, frame)
                    _annotate(frame, detections)
                    for name, conf, _box in detections:
                        if name != "Desconhecido" and name != last_seen and conf > 0.5:
                            last_seen = name
                            state.last_person = name
                            await bus.publish(events.person_recognized(name, conf))
                            log.info("pessoa reconhecida: %s (conf=%.2f)", name, conf)
                # grava o frame anotado (JPEG) para a interface web
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    state.set_frame(buf.tobytes())
                state.fps = cam.fps_measured
            await asyncio.sleep(period)
    except asyncio.CancelledError:
        raise
    finally:
        cam.stop()
