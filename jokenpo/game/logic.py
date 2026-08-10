"""Lógica pura do jogo pedra-papel-tesoura (jokenpô).

Sem hardware, sem I/O, sem LLM — apenas as regras. Fácil de testar
(``tests/test_logic.py``) e reutilizável pelos steps do workflow.

Ponto de vista: os resultados (``vitoria`` / ``derrota`` / ``empate``) são
SEMPRE do ponto de vista do JOGADOR humano.
"""
from __future__ import annotations

import random

# Jogadas canônicas do jogo.
JOGADAS = ("pedra", "papel", "tesoura")

# Emoji de cada jogada (usado no placar visual).
EMOJI = {"pedra": "✊", "papel": "✋", "tesoura": "✌️"}

# Gesto da mão HACKberry que representa cada jogada (protocolo do firmware Thoth).
#   pedra  = punho fechado (FIST)
#   papel  = mão aberta   (OPEN)
#   tesoura= apontar      (POINT)  — os "três dedos" da HACKberry movem juntos,
#            então um V real é impossível; POINT é a aproximação mais legível.
GESTO_ROBO = {"pedra": "fist", "papel": "open", "tesoura": "point"}

# quem_vence[a] == b  ->  a vence b.
_VENCE = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}

# Texto curto do resultado (para exibir e narrar).
RESULT_TEXT = {
    "vitoria": "Você ganhou!",
    "derrota": "Eu ganhei!",
    "empate": "Empate!",
}


def sortear_jogada() -> str:
    """Sorteia aleatoriamente a jogada do robô (justo: ignora o gesto do jogador)."""
    return random.choice(JOGADAS)


def julgar(jogador: str, robo: str) -> str:
    """Compara as jogadas e devolve o resultado do ponto de vista do JOGADOR.

    Retorna ``"vitoria"``, ``"derrota"`` ou ``"empate"``.
    """
    if jogador == robo:
        return "empate"
    return "vitoria" if _VENCE[jogador] == robo else "derrota"


def normalizar_jogada(texto: str) -> str | None:
    """Normaliza texto livre (ex.: saída de um VLM) para uma jogada canônica."""
    t = (texto or "").strip().lower()
    if "pedra" in t or "punho" in t or "fechad" in t or "rock" in t:
        return "pedra"
    if "tesoura" in t or "dois ded" in t or "dedos em v" in t or "scissor" in t:
        return "tesoura"
    if "papel" in t or "abert" in t or "palma" in t or "paper" in t:
        return "papel"
    if t in JOGADAS:
        return t
    return None
