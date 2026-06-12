"""Definição dos agentes Agno e do Orquestrador (Team coordinate).

Atribuição de modelos por papel (via llm/factory.py):
  Orquestrador/Conversação -> Claude ; Visão/STT -> Groq ; Motion/Safety -> Cerebras.

ATENÇÃO a fatos de hardware: o agente Motion só executa gestos de dedos.
"Levantar o braço" e "reorientar a mão para mirar" NÃO são viáveis (não há
atuador de pulso/ombro) — o Safety recusa e sinaliza como gap de hardware.

Os imports do Agno são adiados para dentro de ``build_team`` para permitir
importar este módulo sem o ``agno`` instalado (testes/ambientes mínimos).
"""
from __future__ import annotations

import json
from typing import Any

from thoth.actuation import motion_primitives as motion
from thoth.actuation.serial_client import HandLink
from thoth.core.config import Settings
from thoth.llm.factory import build_model
from thoth.llm.roles import Role
from thoth.safety.limits import LIMITS, is_hardware_gap, validate_angles


def build_team(hand: HandLink, settings: Settings) -> Any:
    """Monta o Team Agno (orquestrador + members). Requer ``agno`` instalado."""
    from agno.agent import Agent
    from agno.team import Team
    from agno.tools import tool

    # ----- TOOLS customizadas -----------------------------------------------

    @tool
    async def executar_gesto(gesto: str) -> str:
        """Executa um gesto físico na MÃO HACKberry.

        Use SEMPRE que o usuário pedir uma ação física da mão (fechar, abrir,
        apontar, pinça, apertar a mão). Gestos válidos: open, fist, point,
        pinch, shake. Esta é a única forma de atuar no hardware.
        """
        g = gesto.strip().lower()
        fn = motion.GESTURES.get(g)
        if fn is None:
            return f"ERRO: gesto desconhecido '{gesto}'. Válidos: {sorted(motion.GESTURES)}."
        ack = await fn(hand)  # chama o cliente serial (actuation)
        return f"ok: gesto '{g}' executado (ACK={ack})"

    @tool
    async def parada_emergencia() -> str:
        """Aborta qualquer movimento e ABRE a mão imediatamente (e-stop lógico).

        Use quando houver risco, comando ambíguo perigoso, ou pedido explícito de parar.
        """
        ack = await hand.stop()
        return f"e-stop acionado: mão aberta (ACK={ack})"

    @tool
    def validar_comando(comando: str, angulos_json: str = "") -> str:
        """Valida se um comando do usuário é fisicamente seguro e viável NESTA mão.

        Use ANTES de qualquer movimento não-nomeado. Rejeita comandos que exigem
        braço/ombro/pulso motorizado (gaps de hardware) e ângulos fora dos limites.
        Retorna 'OK' ou a razão da recusa.
        """
        if is_hardware_gap(comando):
            return (
                "RECUSADO: este hardware é uma MÃO de 3 servos; não há atuador de "
                "pulso/braço/ombro. 'Levantar o braço' ou 'mirar' não são viáveis "
                "(gap de hardware — trabalho futuro)."
            )
        if angulos_json:
            try:
                ang = json.loads(angulos_json)  # nunca regex: sempre json.loads
            except json.JSONDecodeError:
                return "RECUSADO: angulos_json inválido."
            ok, msg = validate_angles(
                ang.get("thumb", LIMITS["thumb"][0]),
                ang.get("index", LIMITS["index"][0]),
                ang.get("other", LIMITS["other"][0]),
            )
            if not ok:
                return f"RECUSADO: {msg}."
        return "OK"

    # ----- AGENTES especialistas --------------------------------------------

    vision_agent = Agent(
        name="Vision",
        role="Interpreta descrições de cena e identidades vindas da visão computacional.",
        model=build_model(Role.VISION, settings),
        instructions=[
            "Você resume o que a câmera vê: pessoas presentes, identidades reconhecidas "
            "e gestos. Seja factual e conciso. Não invente identidades.",
        ],
    )

    motion_agent = Agent(
        name="Motion",
        role="Traduz intenções em gestos físicos da MÃO HACKberry.",
        model=build_model(Role.FAST, settings),
        tools=[executar_gesto, parada_emergencia],
        instructions=[
            "Você comanda uma MÃO de 3 servos de dedos. Só pode: open, fist, point, "
            "pinch, shake. NÃO há atuador de pulso ou braço — nunca prometa levantar o "
            "braço ou reorientar a mão. Antes de mover, confie na validação do Safety.",
        ],
    )

    safety_agent = Agent(
        name="Safety",
        role="Valida segurança e viabilidade física de cada comando antes da execução.",
        model=build_model(Role.FAST, settings),
        tools=[validar_comando],
        instructions=[
            "Você é o portão de segurança. Use validar_comando em TODO pedido de "
            "movimento. Recuse gaps de hardware (braço/ombro/mirar) e ângulos fora dos "
            "limites. Em dúvida, recuse e explique.",
        ],
    )

    nome = settings.assistant_name
    conversation_agent = Agent(
        name="Conversation",
        role="Dialoga em português do Brasil com o usuário de forma natural e breve.",
        model=build_model(Role.CONVERSATION, settings),
        instructions=[
            f"Você é o {nome}, um assistente robótico físico baseado na mão HACKberry.",
            "Responda em PT-BR, com tom cordial e respostas curtas (uma ou duas frases) — "
            "elas serão FALADAS em voz alta, então evite listas e formatação.",
            "Quando cumprimentar alguém reconhecido, use o nome da pessoa.",
            "Não descreva capacidades que o robô não tem (não há braço/pulso motorizado).",
        ],
    )

    # ----- ORQUESTRADOR (Team coordinate) -----------------------------------
    # 'coordinate' (padrão v2): o líder delega às members e sintetiza, mantendo
    # contexto compartilhado. O termo 1.x "collaborate" mapeia para 'coordinate'.
    orchestrator = Team(
        name="ThothOrchestrator",
        mode="coordinate",
        model=build_model(Role.PLANNER, settings),
        members=[vision_agent, safety_agent, motion_agent, conversation_agent],
        instructions=[
            f"Você é o cérebro do {nome}, um robô assistente baseado na MÃO HACKberry.",
            f"O usuário ativa o sistema dizendo '{nome}' e então dá um comando.",
            "Fluxo: (1) entenda o pedido; (2) se envolver movimento, peça ao Safety "
            "para validar ANTES; (3) se aprovado, peça ao Motion para executar; "
            "(4) responda ao usuário pelo Conversation.",
            "Mapeamento de comandos -> hardware real:",
            " - 'aperte minha mão' = gesto SHAKE (fecho suave). Viável.",
            " - 'aponte' = gesto POINT (indicador estendido). Viável, mas a mão NÃO se "
            "   reorienta para mirar uma pessoa (sem braço posicionador).",
            " - 'feche/abra a mão' = FIST/OPEN. Viável.",
            " - 'levante o braço' = NÃO viável (gap de hardware). Explique ao usuário.",
            " - 'quem está na sala?' = pergunte ao Vision; independe da mão.",
            "Para o loop crítico, prefira respostas curtas (menos tokens).",
        ],
    )
    return orchestrator


async def handle_event(orchestrator: Any, event: Any) -> None:
    """Ponte EventBus -> Orquestrador (consome eventos de Visão/Voz)."""
    if event.type == "comando_voz":
        await orchestrator.aprint_response(event.payload["texto"])
    elif event.type == "pessoa_reconhecida":
        nome = event.payload["nome"]
        await orchestrator.aprint_response(
            f"A câmera reconheceu {nome}. Cumprimente-o(a) e ofereça apertar a mão."
        )
