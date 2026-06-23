"""Skills de visão: o Marco olha pela câmera e interpreta o que vê (VLM)."""
from __future__ import annotations

from thoth.agent.skills.registry import tool
from thoth.agent.skills.vision_client import perguntar_visao


@tool(
    "ver_cena",
    "Olha pela câmera e descreve o que está vendo. Use quando perguntarem 'o que você "
    "está vendo', 'o que tem na minha frente', 'descreva o ambiente'.",
)
def ver_cena(_args: dict) -> str:
    return perguntar_visao(
        "Descreva em português, de forma curta e natural (no máximo duas frases), o que você "
        "vê nesta imagem da câmera. Seja direto e objetivo."
    )


@tool(
    "ler_texto",
    "Lê em voz alta o texto que aparece na câmera (placa, papel, etiqueta, bula). "
    "Use para 'leia isto', 'o que está escrito aqui'.",
)
def ler_texto(_args: dict) -> str:
    return perguntar_visao(
        "Transcreva o texto visível nesta imagem e responda APENAS com o texto, em português, "
        "sem comentários. Se não houver texto legível, responda exatamente: "
        "Não vejo nenhum texto legível na câmera.",
        max_tokens=400,
    )


@tool(
    "reconhecer_objetos",
    "Identifica objetos ou pessoas na câmera. Use para 'o que é isto', 'que objeto é esse', "
    "'quantas pessoas tem aqui'.",
)
def reconhecer_objetos(_args: dict) -> str:
    return perguntar_visao(
        "Liste em português, numa única frase curta, os principais objetos e pessoas que você "
        "vê nesta imagem. Se for uma pessoa, descreva brevemente."
    )
