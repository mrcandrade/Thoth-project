import logging
from functools import lru_cache

from agno.models.openai.like import OpenAILike
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude

from config_jokenpo_robotico import (
    CEREBRAS_API_KEY,
    CEREBRAS_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    ANTHROPIC_ROUTER_MODEL,
)

logger = logging.getLogger(__name__)

PROVIDER_CEREBRAS = "cerebras"
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

# Cadeias de fallback (ordem de tentativa).
FALLBACK_CHAIN = [PROVIDER_ANTHROPIC, PROVIDER_OPENAI, PROVIDER_CEREBRAS]
ROUTER_FALLBACK_CHAIN = [PROVIDER_ANTHROPIC, PROVIDER_OPENAI, PROVIDER_CEREBRAS]


# -- Fabricas de modelo (members) -----------------------------------
def _make_cerebras_model():
    if not CEREBRAS_API_KEY:
        return None
    return OpenAILike(id=CEREBRAS_MODEL, api_key=CEREBRAS_API_KEY,
                      base_url="https://api.cerebras.ai/v1")


def _make_openai_model():
    if not OPENAI_API_KEY:
        return None
    return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY, reasoning_effort=None)


def _make_anthropic_model():
    if not ANTHROPIC_API_KEY:
        return None
    return Claude(id=ANTHROPIC_MODEL, api_key=ANTHROPIC_API_KEY,
                  temperature=0.0, thinking=False)


MODEL_FACTORY = {
    PROVIDER_CEREBRAS: _make_cerebras_model,
    PROVIDER_OPENAI: _make_openai_model,
    PROVIDER_ANTHROPIC: _make_anthropic_model,
}


# -- Fabricas de modelo (router/coordenador) ------------------------
def _make_openai_router():
    if not OPENAI_API_KEY:
        return None
    return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY, reasoning_effort=None)


def _make_anthropic_router():
    if not ANTHROPIC_API_KEY:
        return None
    return Claude(id=ANTHROPIC_ROUTER_MODEL, api_key=ANTHROPIC_API_KEY)


def _make_cerebras_router():
    if not CEREBRAS_API_KEY:
        return None
    return OpenAILike(id=CEREBRAS_MODEL, api_key=CEREBRAS_API_KEY,
                      base_url="https://api.cerebras.ai/v1")


ROUTER_MODEL_FACTORY = {
    PROVIDER_OPENAI: _make_openai_router,
    PROVIDER_ANTHROPIC: _make_anthropic_router,
    PROVIDER_CEREBRAS: _make_cerebras_router,
}


def get_provider_name(model) -> str:
    """Identifica o provider de uma instancia de modelo.

    OpenAILike herda de OpenAIChat, entao DEVE ser verificado antes.
    """
    if isinstance(model, Claude):
        return PROVIDER_ANTHROPIC
    if isinstance(model, OpenAILike):
        return PROVIDER_CEREBRAS
    if isinstance(model, OpenAIChat):
        return PROVIDER_OPENAI
    return PROVIDER_CEREBRAS


@lru_cache(maxsize=1)
def _get_prompt_map():
    """Import tardio (evita ciclo) + cache. Mapeia provider -> dict de prompts."""
    from prompts_jokenpo_robotico import OPEN, CLAUDE
    return {
        PROVIDER_CEREBRAS: OPEN,
        PROVIDER_OPENAI: OPEN,
        PROVIDER_ANTHROPIC: CLAUDE,
    }


def _agent_name_to_key(name: str) -> str:
    import re
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def apply_prompts(team, prompt_dict: dict) -> None:
    """Aplica instructions/description do prompt_dict ao team e membros.

    Em mode=coordinate, o coordenador E o team: prompt_dict["coordinator"]
    define as instructions do team. Membros recebem prompt pela chave = slug do nome.
    """
    coord = prompt_dict.get("coordinator")
    if coord:
        team.instructions = coord[0]
    for member in getattr(team, "members", []):
        key = _agent_name_to_key(getattr(member, "name", ""))
        entry = prompt_dict.get(key)
        if not entry:
            continue
        member.instructions = entry[0]
        if len(entry) > 1:
            member.description = entry[1]


def build_model_with_fallback(primary: str = PROVIDER_CEREBRAS):
    """Cria o modelo primario; se faltar key, percorre a cadeia."""
    chain = [primary] + [p for p in FALLBACK_CHAIN if p != primary]
    for provider in chain:
        factory = MODEL_FACTORY.get(provider)
        if not factory:
            continue
        model = factory()
        if model:
            logger.info("Modelo inicializado: %s (%s)", model.id, provider)
            return model
    raise ValueError("Nenhum provider disponivel — verifique suas API keys.")
