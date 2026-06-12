"""Testes das primitivas de movimento (com mão falsa)."""
from __future__ import annotations

from thoth.actuation import motion_primitives as motion
from thoth.actuation.kinematics import frac
from thoth.safety import limits


async def test_abrir_usa_gesto_nomeado(fake_hand):
    ack = await motion.abrir(fake_hand)
    assert ack == "A:P:OPEN"
    assert fake_hand.calls == [("gesture", "OPEN")]


async def test_apertar_a_mao_fecho_suave(fake_hand):
    await motion.apertar_a_mao(fake_hand)
    nome, t, i, o = fake_hand.calls[0]
    assert nome == "set_angles"
    assert (t, i, o) == (
        frac(limits.THUMB_MIN, limits.THUMB_MAX, 0.70),
        frac(limits.INDEX_MIN, limits.INDEX_MAX, 0.70),
        frac(limits.OTHER_MIN, limits.OTHER_MAX, 0.70),
    )
    # nunca esmaga: abaixo do batente máximo
    assert t < limits.THUMB_MAX and i < limits.INDEX_MAX and o < limits.OTHER_MAX


async def test_apontar_estende_indicador(fake_hand):
    await motion.apontar(fake_hand)
    _, t, i, o = fake_hand.calls[0]
    assert i == limits.INDEX_MIN          # indicador estendido (aberto)
    assert o == limits.OTHER_MAX          # demais flexionados


async def test_todas_primitivas_respeitam_limites(fake_hand):
    for fn in (motion.apontar, motion.pinca, motion.apertar_a_mao):
        fake_hand.calls.clear()
        await fn(fake_hand)
        _, t, i, o = fake_hand.calls[0]
        assert limits.in_range(t, i, o), f"{fn.__name__} gerou ângulos fora do limite"


def test_gestures_map_cobre_whitelist():
    assert set(motion.GESTURES) == set(limits.VALID_GESTURES)
