"""Mapa papel -> (provedor, id de modelo).

A atribuição de modelos por papel (ver Seção 1/4 do plano):
  - planner / conversation -> Claude (raciocínio, tool-use, diálogo)
  - vision / stt           -> Groq  (multimodal + Whisper, baixa latência)
  - fast                   -> Cerebras (inferência de altíssima velocidade)

Os IDs vêm da configuração (.env / configs), permitindo override sem mexer
no código. Confirme os IDs atuais nas docs dos provedores antes de produção.
"""
from __future__ import annotations

from enum import Enum

from thoth.core.config import Settings


class Role(str, Enum):
    PLANNER = "planner"
    CONVERSATION = "conversation"
    VISION = "vision"
    STT = "stt"
    FAST = "fast"


# Provedor por papel (o id de modelo vem das Settings).
ROLE_PROVIDER: dict[Role, str] = {
    Role.PLANNER: "anthropic",
    Role.CONVERSATION: "anthropic",
    Role.VISION: "groq",
    Role.STT: "groq",
    Role.FAST: "cerebras",
}


def model_id(role: Role, settings: Settings) -> str:
    return {
        Role.PLANNER: settings.model_planner,
        Role.CONVERSATION: settings.model_conversation,
        Role.VISION: settings.model_vision,
        Role.STT: settings.model_stt,
        Role.FAST: settings.model_fast,
    }[role]
