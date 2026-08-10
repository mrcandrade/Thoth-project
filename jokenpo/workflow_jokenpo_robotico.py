"""Workflow do Jokenpô Robótico (pipeline determinístico Agno).

Uma execução do ``fluxo`` = uma rodada. Os steps passam adiante um dicionário
com o estado da rodada (jogada do jogador, jogada do robô, resultado, placar,
narração e áudio). A lógica pesada (visão, braço, TTS) vive em ``game/`` e é
chamada aqui de forma não-bloqueante (``asyncio.to_thread``).

Fluxo: detectar gesto -> sortear jogada -> mover braço -> julgar -> narrar.
"""
from __future__ import annotations

import asyncio
import base64
import logging

from agno.db.sqlite import SqliteDb
from agno.workflow import Workflow, Step, StepInput, StepOutput

from config_jokenpo_robotico import SQLITE_DB_FILE
from game import config, logic
from game.services import get_services
from game.state import get_state

logger = logging.getLogger("jokenpo.workflow")

db = SqliteDb(db_file=SQLITE_DB_FILE)


def _prev(step_input: StepInput) -> dict:
    """Dicionário acumulado da rodada, vindo do step anterior."""
    c = step_input.previous_step_content
    return dict(c) if isinstance(c, dict) else {}


async def _com_voz(payload: dict, texto: str) -> dict:
    """Sintetiza a narração (bytes p/ o navegador) e, opcionalmente, fala no servidor."""
    svc = get_services()
    payload["audio_b64"] = None
    res = await asyncio.to_thread(svc.narrator.sintetizar, texto)
    if res:
        mime, data = res
        payload["audio_b64"] = base64.b64encode(data).decode("ascii")
        payload["audio_mime"] = mime
    if config.SERVER_AUDIO:
        await asyncio.to_thread(svc.narrator.falar_no_servidor, texto)
    return payload


async def _step_detectar_gesto(step_input: StepInput) -> StepOutput:
    """Detecta o gesto do jogador (MediaPipe + fallback VLM Anthropic) ou manual."""
    svc = get_services()
    add = step_input.additional_data or {}
    manual = add.get("gesto_manual")
    jogada = logic.normalizar_jogada(manual) if manual else await asyncio.to_thread(svc.amostrar_gesto)

    if jogada is None:
        texto = await svc.narrator.comentar_sem_gesto()
        payload = await _com_voz(
            {"player": None, "erro": "gesto_nao_detectado", "narracao": texto,
             "placar": get_state().placar()},
            texto,
        )
        return StepOutput(content=payload, stop=True)  # encerra a rodada (não conta ponto)
    return StepOutput(content={"player": jogada})


async def _step_sortear_jogada(step_input: StepInput) -> StepOutput:
    """Sorteia a jogada do robô (RNG puro — justo, ignora o gesto do jogador)."""
    d = _prev(step_input)
    d["robot"] = logic.sortear_jogada()
    return StepOutput(content=d)


async def _step_mover_braco(step_input: StepInput) -> StepOutput:
    """Move a mão HACKberry para exibir a jogada do robô (best-effort)."""
    d = _prev(step_input)
    svc = get_services()
    robo = d.get("robot")
    d["arm_ok"] = bool(robo) and await asyncio.to_thread(svc.arm.jogar, robo)
    get_state().arm_connected = svc.arm.conectado
    return StepOutput(content=d)


async def _step_julgar_rodada(step_input: StepInput) -> StepOutput:
    """Compara as jogadas, decide o resultado e atualiza o placar."""
    d = _prev(step_input)
    resultado = logic.julgar(d.get("player"), d.get("robot"))
    get_state().registrar_resultado(resultado)
    d["result"] = resultado
    d["result_text"] = logic.RESULT_TEXT[resultado]
    d["placar"] = get_state().placar()
    return StepOutput(content=d)


async def _step_narrar_resultado(step_input: StepInput) -> StepOutput:
    """Narra o resultado e o placar com o Claude (Anthropic) e gera a voz."""
    d = _prev(step_input)
    svc = get_services()
    texto = await svc.narrator.narrar(
        d["player"], d["robot"], d["result"], d["result_text"], d["placar"])
    d["narracao"] = texto
    d["player_emoji"] = logic.EMOJI.get(d.get("player"), "")
    d["robot_emoji"] = logic.EMOJI.get(d.get("robot"), "")
    payload = await _com_voz(d, texto)
    get_state().last_round = {
        k: payload.get(k) for k in
        ("player", "robot", "result", "result_text", "narracao",
         "player_emoji", "robot_emoji", "arm_ok")
    }
    return StepOutput(content=payload)


fluxo = Workflow(
    id="jokenpo_robotico-fluxo",
    name="Jokenpo Robotico",
    description="Uma rodada de pedra, papel e tesoura contra a mão robótica HACKberry.",
    db=db,
    steps=[
        Step(name="detectar gesto", executor=_step_detectar_gesto, max_retries=2, skip_on_failure=False),
        Step(name="sortear jogada", executor=_step_sortear_jogada, max_retries=1, skip_on_failure=False),
        Step(name="mover braco", executor=_step_mover_braco, max_retries=2, skip_on_failure=True),
        Step(name="julgar rodada", executor=_step_julgar_rodada, max_retries=1, skip_on_failure=False),
        Step(name="narrar resultado", executor=_step_narrar_resultado, max_retries=1, skip_on_failure=True),
    ],
    store_events=False,
)
