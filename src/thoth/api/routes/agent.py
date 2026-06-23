"""Modo Agente por voz no navegador (WebSocket `/ws/agent`).

O navegador captura o microfone, detecta o fim da fala (VAD) e envia cada turno
como blob binário. Aqui rodamos o pipeline bloqueante (STT -> LLMBrain com
ferramentas -> edge-tts) numa thread (run_in_executor) e devolvemos, conforme
sai, frames de controle JSON + frames binários MP3 (uma frase por vez). O
navegador toca o áudio e anima a orbe.

Reusa toda a pilha do agente de terminal: persona/memória (chat), skills, STT,
TTS, LLMBrain. A mão (HandLink assíncrona, gerenciada pelo servidor) é acionada
por um adaptador síncrono que agenda no loop do servidor.

Limitações (v1): UMA sessão web ativa por vez (o registry de skills é global);
meia-duplex (o mic é silenciado pelo cliente enquanto o Marco fala).
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from thoth.agent import chat as chat_mod
from thoth.agent import skills
from thoth.agent.llm import LLMBrain
from thoth.agent.stt import STT
from thoth.agent.tts import make_tts
from thoth.core.config import get_settings
from thoth.core.state import get_state

log = logging.getLogger("thoth.api.agent")

router = APIRouter(tags=["agent"])

# Sessão única: o contexto das skills (arm/speaker) é global, então só um
# navegador conversa por vez. A 2ª conexão é recusada.
_session_lock = threading.Lock()

_MIME_EXT = {
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav",
    "audio/mpeg": "mp3", "audio/mp3": "mp3",
}


def _ext_for_mime(mime: str) -> str:
    base = (mime or "").split(";")[0].strip().lower()
    return _MIME_EXT.get(base, "webm")


class AsyncArmAdapter:
    """Fachada síncrona sobre a HandLink assíncrona do servidor (para as skills).

    As skills chamam ``arm.gesture(...)`` de dentro da thread do executor; aqui
    agendamos a corrotina no loop do servidor e esperamos o ACK.
    """

    def __init__(self, hand, loop: asyncio.AbstractEventLoop):
        self._hand = hand
        self._loop = loop

    def _call(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=3.0)

    def gesture(self, name: str) -> str:
        return self._call(self._hand.gesture(name))

    def stop(self) -> str:
        return self._call(self._hand.stop())

    def set_angles(self, thumb: int, index: int, other: int) -> str:
        return self._call(self._hand.set_angles(thumb, index, other))


@router.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket) -> None:
    await websocket.accept()
    if not _session_lock.acquire(blocking=False):
        await websocket.send_json({"type": "error",
                                   "message": "Já existe uma conversa ativa em outra aba."})
        await websocket.close()
        return

    loop = asyncio.get_running_loop()
    settings = get_settings()
    name = settings.assistant_name

    # Inicialização pesada (imports de openai/edge-tts) FORA do event loop: se rodar
    # aqui no loop logo após o accept(), bloqueia o handshake e o cliente dá timeout.
    def _build():
        brain = LLMBrain(settings, chat_mod.build_system_prompt(name),
                         tools=skills.TOOLS, tool_fns=skills.FUNCTIONS)
        return brain, STT(settings), make_tts(settings)

    try:
        brain, stt, tts = await loop.run_in_executor(None, _build)
    except Exception as exc:  # noqa: BLE001
        log.warning("falha ao iniciar o agente web: %s", exc)
        _session_lock.release()
        await websocket.close()
        return

    state = get_state()
    arm = AsyncArmAdapter(state.hand, loop) if state.hand is not None else None
    skills.set_arm(arm)

    out_q: asyncio.Queue = asyncio.Queue()

    def enqueue_json(obj: dict) -> None:
        loop.call_soon_threadsafe(out_q.put_nowait, ("json", obj, None))

    def enqueue_audio(meta: dict, data: bytes) -> None:
        loop.call_soon_threadsafe(out_q.put_nowait, ("audio", meta, data))

    # Lembrete proativo: sintetiza e envia áudio para a sessão (se ainda aberta).
    def web_speak(text: str) -> None:
        try:
            data = tts.synth_bytes(text)
        except Exception:  # noqa: BLE001
            data = None
        if data:
            enqueue_audio({"type": "audio_meta", "seq": -1, "mime": "audio/mpeg", "text": text}, data)

    skills.set_speaker(web_speak)

    state_box = {"mime": "audio/webm;codecs=opus", "ext": "webm"}

    async def sender() -> None:
        """Drena a fila e escreve no websocket (sempre no loop do servidor)."""
        while True:
            kind, obj, data = await out_q.get()
            if kind == "stop":
                break
            try:
                if kind == "json":
                    await websocket.send_json(obj)
                elif kind == "audio":
                    await websocket.send_json(obj)
                    await websocket.send_bytes(data)
            except Exception:  # noqa: BLE001  (cliente caiu)
                break

    sender_task = asyncio.create_task(sender())

    def process_utterance(audio: bytes, ext: str) -> None:
        """Pipeline bloqueante de UM turno (roda numa thread do executor)."""
        enqueue_json({"type": "state", "value": "thinking"})
        try:
            texto = stt.transcribe(audio, filename=f"speech.{ext}")
        except Exception as exc:  # noqa: BLE001
            log.warning("STT falhou: %s", exc)
            enqueue_json({"type": "state", "value": "idle"})
            return
        if not texto.strip():
            enqueue_json({"type": "state", "value": "idle"})
            return
        enqueue_json({"type": "transcript", "text": texto})
        state.last_transcript = texto
        state.push_event("agente_web", {"voce": texto[:60]})

        enqueue_json({"type": "state", "value": "speaking"})
        reply, buf, seq = "", "", 0
        try:
            for delta in brain.stream_reply(texto):
                buf += delta
                reply += delta
                if chat_mod._SENTENCE_END.search(buf):
                    frase, buf = buf.strip(), ""
                    if len(frase) > 1:
                        data = tts.synth_bytes(frase)
                        if data:
                            enqueue_audio({"type": "audio_meta", "seq": seq,
                                           "mime": "audio/mpeg", "text": frase}, data)
                            seq += 1
            if buf.strip():
                data = tts.synth_bytes(buf.strip())
                if data:
                    enqueue_audio({"type": "audio_meta", "seq": seq,
                                   "mime": "audio/mpeg", "text": buf.strip()}, data)
        except Exception as exc:  # noqa: BLE001
            log.warning("pipeline do agente falhou: %s", exc)
        enqueue_json({"type": "reply_text", "text": reply.strip()})
        enqueue_json({"type": "state", "value": "idle"})

    try:
        enqueue_json({"type": "state", "value": "idle"})
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            text_msg = msg.get("text")
            if text_msg is not None:
                try:
                    data = json.loads(text_msg)
                except (ValueError, TypeError):
                    continue
                if data.get("type") == "hello":
                    state_box["mime"] = data.get("mime") or state_box["mime"]
                    state_box["ext"] = _ext_for_mime(state_box["mime"])
                    log.info("agente web: mime=%s", state_box["mime"])
                continue
            audio = msg.get("bytes")
            if audio:
                # o await serializa os turnos; o sender envia o áudio conforme sai
                await loop.run_in_executor(None, process_utterance, audio, state_box["ext"])
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("ws_agent erro: %s", exc)
    finally:
        skills.set_arm(None)
        skills.set_speaker(None)
        loop.call_soon_threadsafe(out_q.put_nowait, ("stop", None, None))
        sender_task.cancel()
        _session_lock.release()
