"""Cérebro do agente — cliente LLM OpenAI-compatible, PLUGÁVEL e com FERRAMENTAS.

Funciona com Cerebras, Groq, Ollama (local) ou qualquer endpoint OpenAI-compatible
(ex.: vLLM servindo o Rio-3.5-Open-397B). Suporta function calling: o LLM decide
quais ferramentas (skills) chamar; nós executamos e devolvemos o resultado.
Trocar de cérebro = mudar LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL no .env.
"""
from __future__ import annotations

import json
import logging

from thoth.core.config import Settings

log = logging.getLogger("thoth.llm")

_BASES = {
    "cerebras": "https://api.cerebras.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",   # LLM local (OpenAI-compatible)
}


def resolve_endpoint(s: Settings) -> tuple[str, str]:
    """Retorna (base_url, api_key) conforme o provedor configurado."""
    p = (s.llm_provider or "cerebras").lower()
    key = {
        "cerebras": s.cerebras_api_key,
        "groq": s.groq_api_key,
    }.get(p) or s.groq_api_key or s.cerebras_api_key or "ollama"
    base = s.llm_base_url or _BASES.get(p) or "http://localhost:8000/v1"
    return base, key


class LLMBrain:
    """Conversa com histórico + function calling (executa as ferramentas do agente)."""

    def __init__(self, settings: Settings, system_prompt: str,
                 tools: list | None = None, tool_fns: dict | None = None,
                 max_history: int = 24, max_tool_rounds: int = 4):
        from openai import OpenAI  # import adiado

        base_url, api_key = resolve_endpoint(settings)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = settings.llm_model
        self.tools = tools or []
        self.tool_fns = tool_fns or {}
        self.max_history = max_history
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]
        log.info("Cérebro: %s @ %s (%d ferramentas)", self.model, base_url, len(self.tools))

    def stream_reply(self, user_text: str):
        """Adiciona a fala do usuário e transmite a resposta (pedaços de texto).

        Se o LLM decidir usar ferramentas, executa-as (sem falar) e continua até
        produzir a resposta final em texto, que é transmitida para o TTS.
        """
        self.messages.append({"role": "user", "content": user_text})

        for _round in range(self.max_tool_rounds):
            content_parts: list[str] = []
            tool_parts: dict[int, dict] = {}

            kwargs = dict(model=self.model, messages=self.messages, stream=True,
                          temperature=0.4, max_tokens=500)
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            for ev in self.client.chat.completions.create(**kwargs):
                if not ev.choices:
                    continue
                delta = ev.choices[0].delta
                if delta.content:
                    content_parts.append(delta.content)
                    yield delta.content
                for tcd in (delta.tool_calls or []):
                    p = tool_parts.setdefault(tcd.index, {"id": "", "name": "", "args": ""})
                    if tcd.id:
                        p["id"] = tcd.id
                    if tcd.function and tcd.function.name:
                        p["name"] = tcd.function.name
                    if tcd.function and tcd.function.arguments:
                        p["args"] += tcd.function.arguments

            if not tool_parts:
                self.messages.append({"role": "assistant", "content": "".join(content_parts)})
                self._trim()
                return

            # registra a decisão de ferramentas e executa cada uma
            calls = [
                {"id": p["id"], "type": "function",
                 "function": {"name": p["name"], "arguments": p["args"] or "{}"}}
                for p in tool_parts.values()
            ]
            self.messages.append({"role": "assistant",
                                  "content": "".join(content_parts) or None,
                                  "tool_calls": calls})
            for p in tool_parts.values():
                result = self._run_tool(p["name"], p["args"])
                self.messages.append({"role": "tool", "tool_call_id": p["id"], "content": result})
            # próximo round: o LLM gera a resposta final usando os resultados

        # excedeu rounds de ferramentas
        self.messages.append({"role": "assistant",
                              "content": "Desculpe, me enrolei aqui. Pode repetir?"})
        yield "Desculpe, me enrolei aqui. Pode repetir?"

    def _run_tool(self, name: str, args_json: str) -> str:
        fn = self.tool_fns.get(name)
        if fn is None:
            return f"ferramenta desconhecida: {name}"
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):   # alguns modelos mandam 'null' p/ ferramenta sem args
            log.warning("argumentos não-dict da ferramenta %s: %r (tipo=%s)",
                        name, args, type(args).__name__)
            args = {}
        try:
            log.info("ferramenta -> %s(%s)", name, args)
            return str(fn(args))
        except Exception as exc:  # noqa: BLE001
            return f"erro na ferramenta {name}: {exc}"

    def _trim(self) -> None:
        if len(self.messages) > self.max_history + 1:
            self.messages = [self.messages[0]] + self.messages[-self.max_history:]
