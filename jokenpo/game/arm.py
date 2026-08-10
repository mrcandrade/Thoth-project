"""Adaptador do braço robótico (mão HACKberry) para o jogo.

Fina camada sobre o ``ArmController`` do Thoth (fachada síncrona e thread-safe
sobre o ``HandLink`` serial). Traduz jogada -> gesto do firmware e nunca afirma
um movimento que o firmware não confirmou (ACK que começa com 'A').
"""
from __future__ import annotations

import logging

from .logic import GESTO_ROBO

log = logging.getLogger("jokenpo.arm")


def _confirmado(ack) -> bool:
    return str(ack).strip().upper().startswith("A")


class ArmAdapter:
    def __init__(self) -> None:
        self._arm = None  # ArmController | None

    @property
    def conectado(self) -> bool:
        return self._arm is not None

    def connect(self) -> bool:
        """Conecta à mão (best-effort). Devolve True se conectou."""
        try:
            from thoth.agent.arm import ArmController

            from .config import settings

            arm = ArmController(settings())
            arm.connect()
            self._arm = arm
            log.info("braço conectado")
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("braço não conectado (%s) — jogo segue sem mão física", exc)
            self._arm = None
            return False

    def jogar(self, jogada: str) -> bool:
        """Move a mão para representar a jogada. True só se o firmware confirmou."""
        if self._arm is None:
            return False
        gesto = GESTO_ROBO.get(jogada)
        if gesto is None:
            return False
        try:
            ack = self._arm.gesture(gesto)
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao mover a mão (%s)", type(exc).__name__)
            return False
        return _confirmado(ack)

    def parar(self) -> bool:
        """Parada de emergência: abre a mão em posição segura."""
        if self._arm is None:
            return False
        try:
            self._arm.stop()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao parar a mão (%s)", type(exc).__name__)
            return False

    def close(self) -> None:
        if self._arm is not None:
            try:
                self._arm.close()
            except Exception:  # noqa: BLE001
                pass
            self._arm = None
