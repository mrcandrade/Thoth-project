"""Skills da mão robótica: gestos, rotinas (acenar/comemorar/demonstrar) e jokenpô.

Segurança: nenhum movimento é afirmado sem o controlador da mão (get_arm). Se a
mão não estiver conectada, as skills dizem isso — nunca fingem ter movido.
"""
from __future__ import annotations

import logging
import random
import time

from thoth.safety.limits import VALID_GESTURES
from thoth.agent.skills.registry import get_arm, tool

log = logging.getLogger("thoth.skills.mao")


def _confirmado(ack) -> bool:
    """True só se o firmware confirmou o comando (ACK começando em 'A')."""
    return str(ack).strip().upper().startswith("A")


@tool(
    "mover_mao",
    "Move a mão robótica fazendo um gesto. Use quando pedirem uma ação física da mão "
    "(abrir, fechar o punho, apontar, pinça, apertar a mão).",
    {"type": "object",
     "properties": {"gesto": {
         "type": "string", "enum": sorted(VALID_GESTURES),
         "description": "open=abrir, fist=fechar punho, point=apontar, pinch=pinça, shake=apertar a mão"}},
     "required": ["gesto"]},
)
def mover_mao(args: dict) -> str:
    gesto = (args.get("gesto") or "").strip().lower()
    if gesto not in VALID_GESTURES:
        return f"Gesto inválido. Use um de: {sorted(VALID_GESTURES)}."
    arm = get_arm()
    if arm is None:
        return "A mão robótica não está conectada agora."
    try:
        ack = arm.gesture(gesto)
    except Exception as exc:  # noqa: BLE001
        return f"Falha ao mover a mão ({type(exc).__name__})."
    if not _confirmado(ack):
        return f"Enviei o gesto '{gesto}', mas a mão não confirmou (resposta: {ack})."
    return f"Pronto, executei o gesto '{gesto}' na mão."


@tool(
    "parar_mao",
    "Parada de emergência: abre a mão imediatamente em posição segura. Use se o usuário "
    "disser 'para', 'pare', 'solta' ou se houver risco.",
)
def parar_mao(_args: dict) -> str:
    arm = get_arm()
    if arm is None:
        return "A mão robótica não está conectada agora."
    try:
        arm.stop()
        return "Parei a mão e abri em posição segura."
    except Exception as exc:  # noqa: BLE001
        return f"Falha ao parar a mão ({type(exc).__name__})."


# --- rotinas (sequências de gestos) ---------------------------------------
_ROTINAS = {
    "acenar": ["open", "fist", "open", "fist", "open"],
    "tchau": ["open", "fist", "open", "fist", "open"],
    "comemorar": ["fist", "open", "fist", "open", "fist", "open"],
    "demonstrar": ["open", "fist", "point", "pinch", "shake", "open"],
}


@tool(
    "fazer_rotina",
    "Executa uma sequência de gestos com a mão: 'acenar' (ou dar tchau), 'comemorar', ou "
    "'demonstrar' (mostra todos os gestos em sequência). Use para 'acena pra mim', "
    "'mostra o que você sabe fazer', 'comemora'.",
    {"type": "object",
     "properties": {"rotina": {"type": "string", "enum": sorted(_ROTINAS),
                               "description": "acenar, tchau, comemorar ou demonstrar"}},
     "required": ["rotina"]},
)
def fazer_rotina(args: dict) -> str:
    nome = (args.get("rotina") or "").strip().lower()
    seq = _ROTINAS.get(nome)
    if seq is None:
        return f"Rotina inválida. Use uma de: {sorted(_ROTINAS)}."
    arm = get_arm()
    if arm is None:
        return "A mão robótica não está conectada agora."
    try:
        for g in seq:
            ack = arm.gesture(g)
            if not _confirmado(ack):
                return f"Comecei a rotina '{nome}', mas a mão não confirmou o gesto '{g}' ({ack})."
            time.sleep(0.7)  # deixa o movimento completar (slew-rate do firmware)
        return f"Pronto, executei a rotina '{nome}'."
    except Exception as exc:  # noqa: BLE001
        return f"Falha ao executar a rotina ({type(exc).__name__})."


# --- pedra, papel e tesoura (jokenpô) -------------------------------------
_GESTO_DA_JOGADA = {"pedra": "fist", "papel": "open", "tesoura": "point"}
_VENCE = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}


def _normaliza_jogada(texto: str) -> str | None:
    t = (texto or "").lower()
    if "pedra" in t or "punho" in t or "fechad" in t:
        return "pedra"
    if "tesoura" in t or "dois ded" in t or "dedos em v" in t:
        return "tesoura"
    if "papel" in t or "abert" in t or "palma" in t:
        return "papel"
    return None


def _resultado(usuario: str, marco: str) -> str:
    if usuario == marco:
        return "Empate!"
    return "Você ganhou!" if _VENCE[usuario] == marco else "Eu ganhei!"


@tool(
    "jogar_pedra_papel_tesoura",
    "Joga pedra, papel e tesoura: olha o seu gesto pela câmera e a mão joga também. "
    "Use para 'vamos jogar pedra papel tesoura', 'joga jokenpô comigo'.",
)
def jogar_pedra_papel_tesoura(_args: dict) -> str:
    arm = get_arm()
    if arm is None:
        return "A mão robótica não está conectada agora, então não consigo jogar."
    from thoth.agent.skills.vision_client import perguntar_visao

    visto = perguntar_visao(
        "A pessoa nesta imagem está fazendo um gesto de jogo: pedra (punho fechado), "
        "papel (mão aberta) ou tesoura (dois dedos em V). Responda com UMA palavra apenas: "
        "pedra, papel ou tesoura.",
        max_tokens=10,
    )
    usuario = _normaliza_jogada(visto)
    if usuario is None:
        return "Não consegui ver seu gesto. Mostre pedra, papel ou tesoura para a câmera e peça de novo."
    marco = random.choice(list(_GESTO_DA_JOGADA))
    try:
        ack = arm.gesture(_GESTO_DA_JOGADA[marco])
    except Exception as exc:  # noqa: BLE001
        return f"Vi que você fez {usuario}, mas falhei ao jogar ({type(exc).__name__})."
    if not _confirmado(ack):
        return f"Vi que você fez {usuario}, mas a mão não confirmou minha jogada ({ack})."
    return f"Você fez {usuario}, eu fiz {marco}. {_resultado(usuario, marco)}"
