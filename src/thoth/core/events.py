"""Tipos de evento canônicos do Thoth (constantes + construtores).

Use estas constantes em vez de strings literais para evitar typos e manter
produtores e consumidores em acordo. Os payloads documentam o contrato.
"""
from __future__ import annotations

from thoth.core.event_bus import Event, Priority

# --- Percepção: visão ---
PERSON_RECOGNIZED = "pessoa_reconhecida"   # payload: {nome: str, confianca: float}
GESTURE_DETECTED = "gesto_detectado"       # payload: {gesto: str, confianca: float}
SCENE_UPDATE = "cena_atualizada"           # payload: {pessoas: int, descricao: str}

# --- Percepção: áudio ---
SPEECH_FINAL = "comando_voz"               # payload: {texto: str}

# --- Atuação / segurança ---
COMMAND_GESTURE = "comando_gesto"          # payload: {gesto: str}
ESTOP = "estop"                            # payload: {origem: str}


def person_recognized(nome: str, confianca: float) -> Event:
    return Event(PERSON_RECOGNIZED, {"nome": nome, "confianca": round(confianca, 2)})


def speech_final(texto: str) -> Event:
    return Event(SPEECH_FINAL, {"texto": texto})


def estop(origem: str = "desconhecida") -> Event:
    return Event(ESTOP, {"origem": origem}, priority=Priority.CRITICAL)
