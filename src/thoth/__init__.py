"""Thoth — assistente robótico multiagente para a mão protética HACKberry.

Camadas (ver docs/plano/PLANO_IMPLEMENTACAO.md):
    perception/ -> core/ (cognição: agents/ + llm/) -> actuation/
A comunicação entre camadas passa SEMPRE pelo event bus (core/event_bus.py)
e pelo orquestrador (agents/team.py). A camada de segurança (safety/) tem
prioridade máxima sobre a atuação.
"""

__version__ = "0.1.0"
