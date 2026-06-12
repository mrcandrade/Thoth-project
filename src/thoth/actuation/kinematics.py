"""Helpers de "cinemática" da mão (de fato: resolução de ângulos por servo).

Para a HACKberry, não há cadeia cinemática espacial — apenas mapeamento de
frações de curso para ângulos de cada servo de dedo, sempre com clamp.
"""
from __future__ import annotations

from thoth.safety.limits import clamp_all


def frac(lo: int, hi: int, f: float) -> int:
    """Interpola entre ``lo`` e ``hi`` pela fração ``f`` ∈ [0, 1], com clamp em f."""
    f = max(0.0, min(1.0, f))
    return int(round(lo + (hi - lo) * f))


def resolve(thumb: int, index: int, other: int) -> tuple[int, int, int]:
    """Aplica o clamp final aos ângulos antes de enviar ao firmware."""
    return clamp_all(thumb, index, other)
