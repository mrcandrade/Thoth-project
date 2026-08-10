"""Serviços do jogo: câmera+visão, braço, locutor e amostragem de gesto.

Singleton central usado pelos steps do workflow e pelo servidor web. A câmera
roda num loop em thread de fundo, publicando o frame anotado (para o vídeo) e o
gesto detectado (num buffer para votação no "já" da contagem).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import Counter, deque

from . import config
from .arm import ArmAdapter
from .narrator import Narrator
from .state import get_state

log = logging.getLogger("jokenpo.services")


class Services:
    def __init__(self) -> None:
        self.state = get_state()
        self.arm = ArmAdapter()
        self.narrator = Narrator()
        self._cam = None
        self._classifier = None
        self._cam_thread: threading.Thread | None = None
        self._running = False
        self._buf: deque[tuple[float, str | None]] = deque(maxlen=60)
        self._buf_lock = threading.Lock()

    # ---- ciclo de vida ---------------------------------------------------
    def startup(self) -> None:
        self.arm.connect()
        self.state.arm_connected = self.arm.conectado
        self._iniciar_camera()

    def shutdown(self) -> None:
        self._running = False
        if self._cam_thread is not None:
            self._cam_thread.join(timeout=1.5)
        if self._classifier is not None:
            self._classifier.close()
        if self._cam is not None:
            self._cam.stop()
        self.arm.close()

    def _iniciar_camera(self) -> None:
        try:
            from thoth.core.config import PROJECT_ROOT
            from thoth.perception.vision.camera import WebcamStream

            from .vision import GestureClassifier

            s = config.settings()
            model = PROJECT_ROOT / "models" / "mediapipe" / "hand_landmarker.task"
            self._classifier = GestureClassifier(model_path=model)
            self._cam = WebcamStream(
                src=s.camera_index, width=s.camera_width, height=s.camera_height
            ).start()
        except Exception as exc:  # noqa: BLE001
            log.warning("câmera/visão indisponível (%s) — só jogada manual", exc)
            self.state.camera_on = False
            return
        self._running = True
        self._cam_thread = threading.Thread(target=self._loop_camera, daemon=True,
                                            name="jokenpo-camera")
        self._cam_thread.start()
        self.state.camera_on = True
        log.info("câmera do jogo ligada (índice %s)", config.settings().camera_index)

    def _loop_camera(self) -> None:
        import cv2

        while self._running:
            frame = self._cam.read()
            if frame is None:
                time.sleep(0.01)
                continue
            annotated, jogada = self._classifier.process(frame)
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self.state.set_frames(buf.tobytes(), frame)
            self.state.last_gesture = jogada
            self.state.hand_seen = jogada is not None
            with self._buf_lock:
                self._buf.append((time.monotonic(), jogada))
            time.sleep(0.015)

    # ---- amostragem do gesto (no "já" da contagem) ----------------------
    def amostrar_gesto(self) -> str | None:
        """Vota no gesto dominante da janela recente; cai no VLM se necessário."""
        agora = time.monotonic()
        with self._buf_lock:
            recentes = [lab for (ts, lab) in self._buf
                        if agora - ts <= config.SAMPLE_WINDOW_S and lab]
        if recentes:
            lab, cnt = Counter(recentes).most_common(1)[0]
            if cnt >= max(2, len(recentes) // 2):
                return lab
        # fallback: VLM da Anthropic sobre o frame bruto atual
        if config.USE_VLM_FALLBACK:
            raw = self.state.get_frame_raw()
            if raw is not None:
                try:
                    from .vision import classificar_com_vlm

                    lab = classificar_com_vlm(raw, config.VLM_MODEL)
                    if lab:
                        log.info("gesto resolvido pelo VLM Anthropic: %s", lab)
                        return lab
                except Exception:  # noqa: BLE001
                    pass
        return None


_services: Services | None = None


def get_services() -> Services:
    """Singleton dos serviços do jogo."""
    global _services
    if _services is None:
        _services = Services()
    return _services
