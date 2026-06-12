"""Smoke test com a mão FÍSICA conectada. Rode com: pytest -m hardware

Exige a placa HACKberry com o firmware hackberry_serial gravado e a porta
serial correta em SERIAL_PORT (.env). Sempre termina com a mão aberta (e-stop).
"""
from __future__ import annotations

import asyncio

import pytest

from thoth.actuation import motion_primitives as motion
from thoth.actuation.serial_client import HandLink
from thoth.core.config import get_settings

pytestmark = pytest.mark.hardware


async def test_open_shake_open():
    settings = get_settings()
    hand = HandLink(port=settings.serial_port, baud=settings.serial_baud)
    await hand.connect()
    try:
        assert (await motion.abrir(hand)).startswith("A:")
        await asyncio.sleep(1.0)
        assert (await motion.apertar_a_mao(hand)).startswith("A:")
        await asyncio.sleep(1.0)
    finally:
        await hand.stop()   # posição segura
        await hand.close()
