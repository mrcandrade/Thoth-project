"""Limites e validação de segurança — FONTE ÚNICA DE VERDADE.

Estes valores DEVEM espelhar os clamps do firmware (firmware/hackberry_serial/
hackberry_serial.ino: THUMB_MIN/MAX, INDEX_MIN/MAX, OTHER_MIN/MAX). Qualquer
recalibração deve ser feita no firmware E aqui — este módulo é importado pela
atuação (motion_primitives) e pela validação do agente Safety.

Convenção de ângulos: menor = ABERTO/ESTENDIDO ; maior = FLEXIONADO/FECHADO.
"""
from __future__ import annotations

# --- Limites de ângulo por servo (graus) — curso seguro (espelha o firmware) ---
THUMB_MIN, THUMB_MAX = 15, 165
INDEX_MIN, INDEX_MAX = 15, 165
OTHER_MIN, OTHER_MAX = 15, 165

LIMITS: dict[str, tuple[int, int]] = {
    "thumb": (THUMB_MIN, THUMB_MAX),
    "index": (INDEX_MIN, INDEX_MAX),
    "other": (OTHER_MIN, OTHER_MAX),
}

# Gestos nomeados aceitos (whitelist). O LLM nunca comanda ângulos arbitrários
# sem passar por validação; gestos fora desta lista são recusados.
VALID_GESTURES: frozenset[str] = frozenset({"open", "fist", "point", "pinch", "shake"})

# Comandos que exigem hardware inexistente (não há atuador de pulso/braço/ombro).
HARDWARE_GAPS: frozenset[str] = frozenset({
    "levantar o braço", "levante o braço", "erguer o braço", "levantar o braco",
    "levante o braco", "mirar", "apontar para mim girando a mão",
})


def clamp(servo: str, value: int) -> int:
    """Restringe ``value`` ao intervalo do servo (thumb/index/other)."""
    lo, hi = LIMITS[servo]
    return max(lo, min(hi, value))


def clamp_all(thumb: int, index: int, other: int) -> tuple[int, int, int]:
    """Aplica o clamp aos três servos de uma vez."""
    return clamp("thumb", thumb), clamp("index", index), clamp("other", other)


def in_range(thumb: int, index: int, other: int) -> bool:
    """True se os três ângulos já estão dentro dos limites (sem precisar de clamp)."""
    return (thumb, index, other) == clamp_all(thumb, index, other)


def validate_angles(thumb: int, index: int, other: int) -> tuple[bool, str]:
    """Valida ângulos absolutos. Retorna (ok, mensagem)."""
    for servo, value in (("thumb", thumb), ("index", index), ("other", other)):
        lo, hi = LIMITS[servo]
        if not (lo <= value <= hi):
            return False, f"{servo}={value} fora do limite [{lo},{hi}]"
    return True, "OK"


def is_hardware_gap(command: str) -> bool:
    """True se o comando exige atuador inexistente (braço/ombro/pulso/mirar)."""
    c = command.strip().lower()
    return any(gap in c for gap in HARDWARE_GAPS)
