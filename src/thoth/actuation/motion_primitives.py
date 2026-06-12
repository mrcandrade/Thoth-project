"""Primitivas de movimento da MÃO HACKberry.

Cada função traduz uma intenção em comandos seriais via ``HandLink``,
respeitando os limites de ``safety.limits`` (fonte única de verdade). Retornam
o ACK do firmware. São consumidas pela tool ``executar_gesto`` do agente Motion.

Convenção de ângulos (espelha hackberry_serial.ino):
  thumb: 10..150   index: 10..160   other: 10..160
  menor = ABERTO/ESTENDIDO   maior = FLEXIONADO/FECHADO
"""
from __future__ import annotations

from thoth.actuation.kinematics import frac
from thoth.actuation.serial_client import HandLink
from thoth.safety.limits import (
    INDEX_MAX,
    INDEX_MIN,
    OTHER_MAX,
    OTHER_MIN,
    THUMB_MAX,
    THUMB_MIN,
)


async def abrir(hand: HandLink) -> str:
    """Mão totalmente aberta (posição segura). Gesto nomeado no firmware."""
    return await hand.gesture("OPEN")


async def fechar_punho(hand: HandLink) -> str:
    """Punho fechado (preensão máxima). Gesto nomeado no firmware."""
    return await hand.gesture("FIST")


async def apontar(hand: HandLink) -> str:
    """Apontar: indicador ESTENDIDO + demais dedos FLEXIONados + polegar recolhido.

    NOTA: a mão aponta no eixo em que estiver fixada manualmente no pulso —
    NÃO consegue se reorientar para mirar uma pessoa (sem braço posicionador).
    """
    return await hand.set_angles(thumb=THUMB_MAX, index=INDEX_MIN, other=OTHER_MAX)


async def pinca(hand: HandLink) -> str:
    """Pinça: polegar contra o indicador (a meio curso), demais dedos abertos."""
    return await hand.set_angles(
        thumb=THUMB_MAX,
        index=frac(INDEX_MIN, INDEX_MAX, 0.5),
        other=OTHER_MIN,
    )


async def apertar_a_mao(hand: HandLink) -> str:
    """'Apertar a mão' = fecho SUAVE (~70% do curso), não esmagador.

    Usa fração do curso em vez do batente para reduzir corrente/pico no servo
    do polegar (que não tem PPTC) e tornar o aperto confortável/seguro.
    """
    return await hand.set_angles(
        thumb=frac(THUMB_MIN, THUMB_MAX, 0.70),
        index=frac(INDEX_MIN, INDEX_MAX, 0.70),
        other=frac(OTHER_MIN, OTHER_MAX, 0.70),
    )


# Mapa de gesto nomeado -> primitiva (consumido pela tool do agente Motion).
GESTURES = {
    "open": abrir,
    "fist": fechar_punho,
    "point": apontar,
    "pinch": pinca,
    "shake": apertar_a_mao,
}


# Exemplo de uso isolado (sem agentes), útil para testes de bancada:
if __name__ == "__main__":
    import asyncio

    async def demo() -> None:
        hand = HandLink(port="COM5")  # ajuste a porta (Linux: /dev/ttyUSB0)
        await hand.connect()
        try:
            print(await abrir(hand))
            await asyncio.sleep(1.0)
            print(await apertar_a_mao(hand))
            await asyncio.sleep(1.0)
            print(await apontar(hand))
            await asyncio.sleep(1.0)
            print(await pinca(hand))
            await asyncio.sleep(1.0)
            print(await abrir(hand))  # sempre termina em posição segura
        finally:
            await hand.close()

    asyncio.run(demo())
