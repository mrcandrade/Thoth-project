"""Pacote de skills (ferramentas) do agente Marco.

Importar este pacote registra todas as ferramentas em ``TOOLS``/``FUNCTIONS``
(via o decorador ``@tool`` de cada módulo). O chat.py usa:
    skills.TOOLS, skills.FUNCTIONS, skills.set_arm, skills.set_speaker, skills.memory
"""
from thoth.agent.skills.registry import (  # noqa: F401
    FUNCTIONS,
    TOOLS,
    get_arm,
    get_speaker,
    set_arm,
    set_speaker,
    tool,
)

# Importa os módulos pelo efeito colateral de registrar suas ferramentas.
from thoth.agent.skills import conversa as _conversa  # noqa: F401,E402
from thoth.agent.skills import mao as _mao  # noqa: F401,E402
from thoth.agent.skills import memory  # noqa: F401,E402  (usado por chat.py)
from thoth.agent.skills import utilidades as _utilidades  # noqa: F401,E402
from thoth.agent.skills import visao as _visao  # noqa: F401,E402

__all__ = [
    "TOOLS", "FUNCTIONS", "set_arm", "get_arm", "set_speaker", "get_speaker", "memory",
]
