"""Fachada SÍNCRONA sobre o HandLink (assíncrono) para o agente de voz.

O loop de voz é síncrono; o HandLink usa asyncio. Esta classe roda o HandLink
num event loop em uma thread de fundo e expõe métodos síncronos (gesture/stop)
que agendam as corrotinas nesse loop. Reaproveita toda a lógica do HandLink
(handshake, ACK, heartbeat, reconexão).
"""
from __future__ import annotations

import asyncio
import logging
import threading

from thoth.actuation.serial_client import HandLink
from thoth.core.config import Settings

log = logging.getLogger("thoth.arm")


class ArmController:
    def __init__(self, settings: Settings):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="arm-loop")
        self._thread.start()
        self.hand = HandLink(
            port=settings.serial_port,
            baud=settings.serial_baud,
            heartbeat_period=settings.heartbeat_period,
        )

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _call(self, coro, timeout: float = 5.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def connect(self, timeout: float = 8.0) -> None:
        """Conecta à mão; levanta exceção se não houver hardware na porta."""
        self._call(asyncio.wait_for(self.hand.connect(), timeout=timeout), timeout=timeout + 1)
        log.info("braço conectado")

    def gesture(self, name: str) -> str:
        return self._call(self.hand.gesture(name), timeout=3.0)

    def set_angles(self, thumb: int, index: int, other: int) -> str:
        return self._call(self.hand.set_angles(thumb, index, other), timeout=3.0)

    def stop(self) -> str:
        return self._call(self.hand.stop(), timeout=3.0)

    def close(self) -> None:
        try:
            self._call(self.hand.close(), timeout=2.0)
        except Exception:  # noqa: BLE001
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
