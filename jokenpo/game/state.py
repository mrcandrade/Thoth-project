"""Estado do jogo compartilhado entre a visão, o workflow e a web (thread-safe).

Guarda o placar, a última rodada e o último frame anotado da câmera (para o
stream de vídeo). A captura roda numa thread; a web e o workflow leem daqui.
"""
from __future__ import annotations

import threading
from typing import Any

import numpy as np


class GameState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # placar
        self.jogador = 0
        self.robo = 0
        self.empates = 0
        # última rodada (dict serializável) e status
        self.last_round: dict[str, Any] | None = None
        self.arm_connected = False
        self.camera_on = False
        self.hand_seen = False
        self.last_gesture: str | None = None
        # frames (anotado em JPEG p/ o vídeo; bruto em BGR p/ o VLM)
        self._frame_jpeg: bytes | None = None
        self._frame_raw: np.ndarray | None = None

    # ---- placar ----------------------------------------------------------
    def registrar_resultado(self, resultado: str) -> None:
        with self._lock:
            if resultado == "vitoria":
                self.jogador += 1
            elif resultado == "derrota":
                self.robo += 1
            else:
                self.empates += 1

    def placar(self) -> dict[str, int]:
        with self._lock:
            return {"jogador": self.jogador, "robo": self.robo, "empates": self.empates}

    def reset(self) -> None:
        with self._lock:
            self.jogador = self.robo = self.empates = 0
            self.last_round = None

    # ---- frames ----------------------------------------------------------
    def set_frames(self, jpeg: bytes | None, raw: "np.ndarray | None") -> None:
        with self._lock:
            if jpeg is not None:
                self._frame_jpeg = jpeg
            if raw is not None:
                self._frame_raw = raw

    def get_frame_jpeg(self) -> bytes | None:
        with self._lock:
            return self._frame_jpeg

    def get_frame_raw(self) -> "np.ndarray | None":
        with self._lock:
            return None if self._frame_raw is None else self._frame_raw.copy()

    # ---- snapshot p/ a web ----------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "placar": {"jogador": self.jogador, "robo": self.robo, "empates": self.empates},
                "ultima_rodada": self.last_round,
                "braco_conectado": self.arm_connected,
                "camera_ligada": self.camera_on,
                "mao_visivel": self.hand_seen,
                "gesto_atual": self.last_gesture,
            }


_state: GameState | None = None


def get_state() -> GameState:
    """Singleton do estado do jogo."""
    global _state
    if _state is None:
        _state = GameState()
    return _state
