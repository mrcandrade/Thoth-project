"""Bootstrap do Mendes: sobe mão + agentes + visão + voz + interface web.

Um único processo e event loop. Tolerante a dependências/hardware ausentes:
cada camada que não puder iniciar registra um aviso e o resto segue — assim você
sobe o sistema incrementalmente, fase a fase.

    python -m thoth        # ou: just run
    -> dashboard em http://127.0.0.1:8000
"""
from __future__ import annotations

import asyncio
import logging

from thoth.actuation.serial_client import HandLink
from thoth.core.config import Settings, get_settings
from thoth.core.event_bus import Event, EventBus
from thoth.core.logging import setup_logging
from thoth.core.state import get_state
from thoth.voice.tts import Speaker

log = logging.getLogger("thoth.app")


async def _connect_hand(settings: Settings) -> HandLink | None:
    hand = HandLink(
        port=settings.serial_port,
        baud=settings.serial_baud,
        heartbeat_period=settings.heartbeat_period,
    )
    try:
        await asyncio.wait_for(hand.connect(), timeout=8.0)
        return hand
    except Exception as exc:  # noqa: BLE001
        log.warning("Mão não conectada (%s). Seguindo SEM atuação física.", exc)
        return None


def _build_orchestrator(hand: HandLink | None, settings: Settings):
    if hand is None:
        log.warning("Sem mão conectada — orquestrador de movimento limitado.")
    try:
        from thoth.agents.team import build_team

        # build_team aceita None como mão (as tools de movimento só falham se chamadas).
        return build_team(hand, settings) if hand is not None else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Orquestrador Agno indisponível (%s).", exc)
        return None


def _reply_text(resp) -> str:
    """Extrai o texto de uma resposta do Agno (RunOutput) de forma defensiva."""
    return (getattr(resp, "content", None) or str(resp)).strip()


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    state = get_state()
    state.managed_externally = True  # a API não vai gerenciar a mão; nós gerenciamos
    log.info("Iniciando %s (env=%s)…", settings.assistant_name, settings.thoth_env)

    bus = EventBus()
    bus.start()

    hand = await _connect_hand(settings)
    state.hand = hand
    orchestrator = _build_orchestrator(hand, settings)
    speaker = Speaker(rate=settings.tts_rate, voice_hint=settings.tts_voice_hint,
                      enabled=settings.tts_enabled)
    nome = settings.assistant_name

    # ---- handlers de evento ------------------------------------------------
    async def on_command(event: Event) -> None:
        texto = event.payload.get("texto", "")
        try:
            if orchestrator is not None:
                resp = await orchestrator.arun(texto)
                reply = _reply_text(resp)
            else:
                reply = f"{nome} ouviu: {texto}. (Cérebro de IA indisponível neste momento.)"
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao processar comando: %s", exc)
            reply = "Desculpe, tive um problema ao processar isso."
        speaker.say(reply)
        state.push_event("resposta", {"texto": reply})

    async def on_person(event: Event) -> None:
        pessoa = event.payload.get("nome", "alguém")
        try:
            if orchestrator is not None:
                resp = await orchestrator.arun(
                    f"A câmera reconheceu {pessoa}. Cumprimente-o(a) brevemente pelo nome "
                    f"e ofereça apertar a mão."
                )
                reply = _reply_text(resp)
            else:
                reply = f"Olá, {pessoa}! Que bom te ver."
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao cumprimentar: %s", exc)
            reply = f"Olá, {pessoa}!"
        speaker.say(reply)
        state.push_event("resposta", {"texto": reply})

    bus.subscribe("comando_voz", on_command)
    bus.subscribe("pessoa_reconhecida", on_person)

    # ---- tarefas (percepção + web) -----------------------------------------
    tasks: list[asyncio.Task] = []

    async def _safe_loop(coro_factory, nome_loop: str) -> None:
        try:
            await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Loop '%s' não iniciou (%s).", nome_loop, exc)

    from thoth.perception.audio.pipeline import voice_loop
    from thoth.perception.vision.pipeline import vision_loop

    tasks.append(asyncio.create_task(
        _safe_loop(lambda: vision_loop(bus, settings), "visão"), name="vision"))
    tasks.append(asyncio.create_task(
        _safe_loop(lambda: voice_loop(bus, settings), "voz"), name="voice"))

    # servidor web (dashboard + telemetria) no mesmo event loop
    try:
        import uvicorn

        from thoth.api.server import app as fastapi_app

        config = uvicorn.Config(fastapi_app, host=settings.api_host,
                                port=settings.api_port, log_level="warning")
        server = uvicorn.Server(config)
        tasks.append(asyncio.create_task(server.serve(), name="web"))
        log.info("Dashboard: http://%s:%d", settings.api_host, settings.api_port)
    except Exception as exc:  # noqa: BLE001
        log.warning("Servidor web não iniciou (%s).", exc)

    if speaker.enabled:
        speaker.say(f"{nome} iniciado e pronto.")
    log.info("%s no ar. Ctrl+C para encerrar.", nome)
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        log.info("Encerrando…")
        for t in tasks:
            t.cancel()
        speaker.stop()
        if hand is not None:
            try:
                await hand.stop()  # posição segura: mão aberta
            except Exception:  # noqa: BLE001
                pass
            await hand.close()
        await bus.stop()


def main() -> None:
    """Entry point síncrono (console_script `thoth`)."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
