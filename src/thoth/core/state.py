"""Estado compartilhado da aplicação (singleton).

Faz a ponte entre os loops assíncronos (visão, voz, agentes) e a interface web
(FastAPI): a visão grava aqui o último frame anotado; os loops empurram eventos;
o servidor web lê tudo para o dashboard e o stream de vídeo.

Acesso thread-safe ao frame (a captura roda em thread separada).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


@dataclass
class AppState:
    # Hardware (preenchido por app.py ou pelo lifespan da API).
    hand: Any = None
    managed_externally: bool = False  # True => o lifespan da API não gerencia a mão

    # Último frame JPEG anotado (para o stream MJPEG da web).
    latest_jpeg: bytes | None = None

    # Telemetria de voz/visão.
    last_transcript: str = ""
    last_person: str | None = None
    listening: bool = False
    awaiting_command: bool = False
    fps: float = 0.0

    # Log de eventos recentes (para o dashboard).
    events: deque = field(default_factory=lambda: deque(maxlen=120))

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- frame ----
    def set_frame(self, jpeg: bytes) -> None:
        with self._lock:
            self.latest_jpeg = jpeg

    def get_frame(self) -> bytes | None:
        with self._lock:
            return self.latest_jpeg

    # ---- eventos ----
    def push_event(self, tipo: str, dados: dict | None = None) -> None:
        self.events.append({"ts": time.time(), "tipo": tipo, "dados": dados or {}})

    # ---- snapshot para o websocket ----
    def snapshot(self) -> dict:
        hand_status = None
        if self.hand is not None:
            st = getattr(self.hand, "last_status", None)
            connected = bool(getattr(getattr(self.hand, "_connected", None), "is_set", lambda: False)())
            hand_status = {
                "conectada": connected,
                "thumb": getattr(st, "thumb", None),
                "index": getattr(st, "index", None),
                "other": getattr(st, "other", None),
                "modo": getattr(st, "mode", None),
            }
        return {
            "mao": hand_status,
            "transcricao": self.last_transcript,
            "ultima_pessoa": self.last_person,
            "escutando": self.listening,
            "aguardando_comando": self.awaiting_command,
            "fps": round(self.fps, 1),
            "eventos": list(self.events)[-30:],
        }


@lru_cache(maxsize=1)
def get_state() -> AppState:
    """Retorna o estado global (singleton)."""
    return AppState()
