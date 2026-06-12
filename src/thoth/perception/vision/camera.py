"""Captura de webcam desacoplada do consumo (latest-frame), com medição de FPS.

``cap.read()`` é bloqueante. Uma thread dedicada mantém apenas o último frame;
o loop de inferência consome esse frame sem travar. No Windows, ``CAP_DSHOW``
reduz a latência de abertura; ``BUFFERSIZE=1`` evita frames atrasados.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np


class WebcamStream:
    def __init__(self, src: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        # CAP_DSHOW: backend DirectShow no Windows (abertura mais rápida/estável)
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # mantém só o frame mais recente

        if not self.cap.isOpened():
            raise RuntimeError(f"não foi possível abrir a câmera src={src}")

        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # medição de FPS efetivo
        self._tick = time.monotonic()
        self._count = 0
        self.fps_measured = 0.0

    def start(self) -> "WebcamStream":
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _loop(self) -> None:
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = frame
            self._count += 1
            now = time.monotonic()
            if now - self._tick >= 1.0:
                self.fps_measured = self._count / (now - self._tick)
                self._tick, self._count = now, 0

    def read(self) -> np.ndarray | None:
        """Retorna uma cópia do último frame (ou None se ainda não há frame)."""
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.cap.release()


# Demo de bancada: NÃO rode 5 modelos em série no mesmo frame a 30 FPS na CPU.
if __name__ == "__main__":
    cam = WebcamStream().start()
    try:
        n = 0
        while True:
            frame = cam.read()
            if frame is None:
                continue
            n += 1
            if n % 5 == 0:
                print(f"FPS captura ≈ {cam.fps_measured:.1f}")
            cv2.imshow("thoth", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.stop()
        cv2.destroyAllWindows()
