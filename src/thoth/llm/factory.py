"""Fábrica de modelos: ÚNICO ponto que instancia Claude/Groq/Cerebras do Agno.

Os agentes recebem o modelo pronto (injeção), nunca o criam. Os imports do
Agno são adiados para dentro de ``build_model`` para que importar este módulo
não exija o ``agno`` instalado (útil em testes que não tocam os LLMs).
"""
from __future__ import annotations

from typing import Any

from thoth.core.config import Settings
from thoth.llm.roles import ROLE_PROVIDER, Role, model_id


def build_model(role: Role, settings: Settings) -> Any:
    """Constrói o modelo Agno apropriado para o ``role``.

    Levanta ``RuntimeError`` se faltar a chave de API do provedor escolhido.
    """
    provider = ROLE_PROVIDER[role]
    mid = model_id(role, settings)

    if provider == "anthropic":
        from agno.models.anthropic import Claude

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY ausente para papel " + role.value)
        return Claude(id=mid, api_key=settings.anthropic_api_key)

    if provider == "groq":
        from agno.models.groq import Groq

        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY ausente para papel " + role.value)
        return Groq(id=mid, api_key=settings.groq_api_key)

    if provider == "cerebras":
        from agno.models.cerebras import Cerebras

        if not settings.cerebras_api_key:
            raise RuntimeError("CEREBRAS_API_KEY ausente para papel " + role.value)
        return Cerebras(id=mid, api_key=settings.cerebras_api_key)

    raise ValueError(f"provedor desconhecido: {provider}")
