"""Registro central das ferramentas (skills) do agente + contexto de runtime.

Cada módulo de skill usa o decorador ``@tool(...)`` para se registrar; o pacote
agrega tudo em ``TOOLS`` (schemas OpenAI) e ``FUNCTIONS`` (nome -> callable).

O contexto de runtime (braço robótico e "voz"/speaker) é injetado pelo chat.py:
- ``set_arm`` liga o controlador da mão (para as skills que a movem);
- ``set_speaker`` liga a função de fala (para o lembrete avisar por voz).
"""
from __future__ import annotations

import logging

log = logging.getLogger("thoth.skills")

TOOLS: list[dict] = []
FUNCTIONS: dict = {}


def tool(name: str, description: str, parameters: dict | None = None):
    """Decorador: registra ``fn`` como ferramenta do agente (function calling)."""
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}},
        },
    }

    def deco(fn):
        TOOLS.append(schema)
        FUNCTIONS[name] = fn
        return fn

    return deco


# --- contexto de runtime (injetado por chat.py) ---------------------------
_ctx: dict = {"arm": None, "speaker": None}


def set_arm(controller) -> None:
    _ctx["arm"] = controller


def get_arm():
    return _ctx["arm"]


def set_speaker(fn) -> None:
    """Registra a função usada para falar de forma proativa (ex.: lembrete)."""
    _ctx["speaker"] = fn


def get_speaker():
    return _ctx["speaker"]
