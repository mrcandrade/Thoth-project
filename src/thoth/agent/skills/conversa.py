"""Skills de conversa/personalidade: memória do usuário, piadas e curiosidades."""
from __future__ import annotations

import random

from thoth.agent.skills.memory import add_fact, set_user_name
from thoth.agent.skills.registry import tool


@tool(
    "lembrar",
    "Guarda na memória uma informação ou preferência do usuário, para você lembrar nas "
    "próximas conversas. Use quando ele disser 'meu nome é...', 'lembre que eu gosto de...', "
    "'anota que...'.",
    {"type": "object",
     "properties": {
         "nome": {"type": "string", "description": "o nome do usuário, se ele disser"},
         "fato": {"type": "string", "description": "a informação/preferência a lembrar"}},
     },
)
def lembrar(args: dict) -> str:
    nome = (args.get("nome") or "").strip()
    fato = (args.get("fato") or "").strip()
    anotados = []
    if nome:
        set_user_name(nome)
        anotados.append(f"seu nome é {nome}")
    if fato:
        add_fact(fato)
        anotados.append(fato)
    if not anotados:
        return "Não entendi o que devo lembrar."
    return "Anotado, vou lembrar: " + "; ".join(anotados) + "."


_PIADAS = [
    "Por que o livro de matemática estava triste? Porque tinha muitos problemas.",
    "O que o zero disse para o oito? Belo cinto!",
    "Qual é o cúmulo da força? Tocar piano com as costas das mãos. Eu até tentaria, mas só tenho uma mão.",
    "Por que o computador foi ao médico? Porque estava com um vírus.",
    "O que é um pontinho amarelo no céu? Um Yellowcóptero.",
    "Por que a plantinha não anda? Porque ela está enraizada na ideia.",
    "Qual é o contrário de volátil? Vem cá, sua tília.",
]

_CURIOSIDADES = [
    "O polvo tem três corações e sangue azul.",
    "Um raio é cerca de cinco vezes mais quente que a superfície do Sol.",
    "O mel não estraga: já acharam potes comestíveis com milhares de anos.",
    "Os flamingos nascem cinzas e ficam rosa por causa do que comem.",
    "Santos Dumont fez o primeiro voo público com o 14-bis em 1906, em Paris.",
    "O coração de uma baleia-azul é tão grande que um humano caberia em algumas artérias.",
    "A mão humana tem 27 ossos. Eu, como mão robótica, me viro com bem menos peças.",
]


@tool("contar_piada", "Conta uma piada curta. Use quando pedirem uma piada.")
def contar_piada(_args: dict) -> str:
    return random.choice(_PIADAS)


@tool("curiosidade", "Conta uma curiosidade interessante. Use para 'me conta uma curiosidade'.")
def curiosidade(_args: dict) -> str:
    return random.choice(_CURIOSIDADES)
