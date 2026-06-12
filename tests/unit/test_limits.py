"""Testes dos limites de segurança (fonte única de verdade)."""
from __future__ import annotations

from thoth.safety import limits


def test_clamp_respeita_intervalo():
    assert limits.clamp("thumb", 999) == limits.THUMB_MAX
    assert limits.clamp("thumb", -10) == limits.THUMB_MIN
    assert limits.clamp("index", 100) == 100


def test_clamp_all():
    assert limits.clamp_all(999, -5, 80) == (limits.THUMB_MAX, limits.INDEX_MIN, 80)


def test_in_range():
    assert limits.in_range(80, 80, 80) is True
    assert limits.in_range(999, 80, 80) is False


def test_validate_angles():
    ok, _ = limits.validate_angles(80, 80, 80)
    assert ok is True
    ok, msg = limits.validate_angles(999, 80, 80)
    assert ok is False and "thumb" in msg


def test_hardware_gap_detecta_braco():
    assert limits.is_hardware_gap("Por favor levante o braço") is True
    assert limits.is_hardware_gap("aperte minha mão") is False
