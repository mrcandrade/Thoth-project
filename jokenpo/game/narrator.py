"""Locutor do jogo: narração e saudação com um agente Agno + Claude (Anthropic).

O agente usa o modelo da Anthropic (via ``providers_jokenpo_robotico``, cadeia de
fallback com anthropic em primeiro). A síntese de voz (TTS) reaproveita o motor
do Thoth (edge-tts online ou Piper offline), devolvendo bytes de áudio para o
navegador tocar.

Degrada com elegância: sem chave/no offline, cai em frases prontas e/ou sem
áudio — o jogo continua funcionando.
"""
from __future__ import annotations

import logging

log = logging.getLogger("jokenpo.narrator")

_PERSONA = (
    "Você é o locutor e árbitro do Jokenpô Robótico: uma mão robótica de código "
    "aberto que joga pedra, papel e tesoura com as pessoas. Fale em português do "
    "Brasil, com energia de locutor esportivo e bom humor. Suas respostas serão "
    "faladas em voz alta, então escreva UMA a DUAS frases curtas e naturais — sem "
    "listas, markdown, emojis, símbolos ou formatação. Provoque de leve, com "
    "carinho, quando o robô ganhar; seja gentil e elogie quando o jogador ganhar; "
    "anime nos empates. Mencione o placar de forma natural quando fizer sentido. "
    "Nunca invente jogadas: baseie-se apenas no que for informado."
)


class Narrator:
    def __init__(self) -> None:
        self._agent = None
        self._agent_ready = False
        self._tts = None
        self._tts_ready = False

    # ---- agente (Claude via Agno) ---------------------------------------
    def _get_agent(self):
        if self._agent_ready:
            return self._agent
        self._agent_ready = True
        try:
            from agno.agent import Agent

            from providers_jokenpo_robotico import build_model_with_fallback

            model = build_model_with_fallback(primary="anthropic")
            self._agent = Agent(
                name="Locutor do Jokenpô",
                model=model,
                instructions=_PERSONA,
                markdown=False,
            )
            log.info("locutor (Claude/Anthropic) pronto: %s", getattr(model, "id", "?"))
        except Exception as exc:  # noqa: BLE001
            log.warning("locutor LLM indisponível (%s) — usando frases prontas", exc)
            self._agent = None
        return self._agent

    async def _pensar(self, prompt: str, fallback: str) -> str:
        agent = self._get_agent()
        if agent is None:
            return fallback
        try:
            resp = await agent.arun(prompt)
            texto = (getattr(resp, "content", "") or "").strip()
            return texto or fallback
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao narrar com o LLM (%s)", type(exc).__name__)
            return fallback

    async def narrar(self, jogador: str, robo: str, resultado: str,
                     result_text: str, placar: dict) -> str:
        # "resultado" é o código (vitoria/derrota/empate, do ponto de vista do
        # jogador). Traduzimos para quem venceu de forma inequívoca, senão o LLM
        # confunde "Eu/Você" (o locutor é o próprio robô).
        quem_venceu = {
            "vitoria": "o JOGADOR humano venceu esta rodada",
            "derrota": "VOCÊ (o robô) venceu esta rodada",
            "empate": "esta rodada EMPATOU",
        }[resultado]
        fallback = f"Você fez {jogador}, eu fiz {robo}. {result_text} " \
                   f"Placar: você {placar['jogador']}, eu {placar['robo']}."
        prompt = (
            f"Rodada de jokenpô. O jogador jogou {jogador}. Você, o robô, jogou {robo}. "
            f"Resultado: {quem_venceu}. Placar agora: jogador {placar['jogador']}, "
            f"robô {placar['robo']}, empates {placar['empates']}. "
            "Narre esta rodada em uma ou duas frases, com energia."
        )
        return await self._pensar(prompt, fallback)

    async def saudar(self, placar: dict) -> str:
        fallback = ("Olá! Eu sou a mão robótica. Vamos jogar pedra, papel e tesoura? "
                    "Faça seu gesto para a câmera e clique em jogar.")
        prompt = (
            "Cumprimente o jogador de forma calorosa e o convide para uma partida de "
            "pedra, papel e tesoura contra você, a mão robótica. "
            f"Placar atual: jogador {placar['jogador']}, robô {placar['robo']}."
        )
        return await self._pensar(prompt, fallback)

    async def comentar_sem_gesto(self) -> str:
        fallback = ("Não consegui ver seu gesto. Mostre pedra, papel ou tesoura "
                    "para a câmera e tente de novo.")
        return await self._pensar(
            "Você não conseguiu identificar o gesto do jogador na câmera. Peça, com "
            "bom humor e em uma frase, para ele mostrar pedra, papel ou tesoura de novo.",
            fallback,
        )

    # ---- voz (TTS do Thoth) ---------------------------------------------
    def _get_tts(self):
        if self._tts_ready:
            return self._tts
        self._tts_ready = True
        try:
            from thoth.agent.tts import make_tts

            from .config import settings

            self._tts = make_tts(settings())
        except Exception as exc:  # noqa: BLE001
            log.warning("TTS indisponível (%s) — jogo segue sem voz", exc)
            self._tts = None
        return self._tts

    def sintetizar(self, texto: str) -> tuple[str, bytes] | None:
        """Sintetiza a fala e devolve (mime, bytes) para o navegador tocar."""
        tts = self._get_tts()
        if tts is None or not (texto or "").strip():
            return None
        try:
            data = tts.synth_bytes(texto)
        except Exception as exc:  # noqa: BLE001
            log.warning("síntese de voz falhou (%s)", type(exc).__name__)
            return None
        if not data:
            return None
        # edge-tts devolve MP3; Piper devolve WAV.
        mime = "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"
        return mime, data

    def falar_no_servidor(self, texto: str) -> None:
        """Toca a fala no alto-falante do servidor (opcional)."""
        tts = self._get_tts()
        if tts is not None and (texto or "").strip():
            try:
                tts.say(texto)
            except Exception:  # noqa: BLE001
                pass
