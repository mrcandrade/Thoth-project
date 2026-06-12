"""Pipeline de voz do Mendes.

Dois modos de ativação (config `WAKE_MODE`):
  - "phrase" (padrão): escuta contínua -> Silero VAD segmenta a fala -> Groq
    Whisper transcreve -> se a transcrição contém a palavra "Mendes", o texto
    APÓS ela é tratado como comando. Funciona com qualquer nome, sem treinar
    um modelo de wake word.
  - "openwakeword": modelo dedicado de wake word ativa a escuta (exige modelo).

Microfone: usa o dispositivo PADRÃO do Windows quando `MIC_DEVICE` está vazio.
"""
from __future__ import annotations

import asyncio
import io
import logging
import wave

import numpy as np

from thoth.core import events
from thoth.core.config import Settings
from thoth.core.event_bus import EventBus
from thoth.core.state import get_state

log = logging.getLogger("thoth.voice")

SAMPLE_RATE = 16_000  # Whisper e Silero operam a 16 kHz
FRAME = 512           # tamanho de frame para VAD (~32 ms a 16 kHz)
SILENCE_TAIL_S = 0.6  # silêncio que fecha um segmento de fala


def _pcm_to_wav_bytes(pcm: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    """Empacota PCM int16 mono em um WAV em memória (formato aceito pela Groq)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _resolve_device(mic_device: str | None):
    """Converte a config do microfone para o formato do sounddevice (None/int/str)."""
    if not mic_device:
        return None  # dispositivo padrão do Windows
    return int(mic_device) if mic_device.isdigit() else mic_device


class VoicePipeline:
    def __init__(self, api_key: str, groq_model: str = "whisper-large-v3",
                 mic_device: str | None = None, wakeword: str = "hey_jarvis"):
        from groq import Groq
        from silero_vad import VADIterator, load_silero_vad

        self.client = Groq(api_key=api_key)
        self.groq_model = groq_model
        self.device = _resolve_device(mic_device)
        self.vad_model = load_silero_vad()
        self.vad = VADIterator(self.vad_model, sampling_rate=SAMPLE_RATE)
        self._wakeword = wakeword
        self._wake = None  # carregado sob demanda no modo openwakeword

    def _transcribe(self, pcm: np.ndarray) -> str | None:
        if pcm.size < SAMPLE_RATE // 3:  # < ~0,3 s -> provavelmente ruído
            return None
        wav_bytes = _pcm_to_wav_bytes(pcm)
        resp = self.client.audio.transcriptions.create(
            file=("speech.wav", wav_bytes),
            model=self.groq_model,  # "whisper-large-v3" (PT-BR)
            language="pt",
            response_format="text",
        )
        text = resp if isinstance(resp, str) else getattr(resp, "text", "")
        return text.strip() or None

    def listen_segment(self, max_seconds: float = 15.0) -> str | None:
        """Captura UM segmento de fala (VAD) e transcreve. Bloqueante."""
        import sounddevice as sd

        self.vad.reset_states()
        collected: list[np.ndarray] = []
        in_speech = False
        max_frames = int(max_seconds * SAMPLE_RATE / FRAME)

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=FRAME, device=self.device) as stream:
            for _ in range(max_frames):
                block, _ = stream.read(FRAME)
                samples = block.reshape(-1).astype(np.int16)
                f32 = samples.astype(np.float32) / 32768.0  # Silero: float32 [-1,1]
                res = self.vad(f32, return_seconds=False)
                if res is not None and "start" in res:
                    in_speech = True
                if in_speech:
                    collected.append(samples)
                    if res is not None and "end" in res:
                        break

        self.vad.reset_states()
        if not collected:
            return None
        return self._transcribe(np.concatenate(collected))


async def voice_loop(bus: EventBus, settings: Settings) -> None:
    """Loop de voz: detecta 'Mendes' e publica o comando no bus."""
    if not settings.groq_api_key:
        log.warning("GROQ_API_KEY ausente — pipeline de voz desativado.")
        return

    state = get_state()
    vp = VoicePipeline(
        api_key=settings.groq_api_key,
        groq_model=settings.model_stt,
        mic_device=settings.mic_device,
        wakeword=settings.wakeword_model,
    )
    wake = settings.wake_word.lower()
    log.info("Voz pronta — diga '%s' para ativar.", settings.assistant_name)

    awaiting_command = False
    try:
        while True:
            state.listening = True
            state.awaiting_command = awaiting_command
            text = await asyncio.to_thread(vp.listen_segment)
            if not text:
                continue
            state.last_transcript = text
            state.push_event("transcricao", {"texto": text})
            low = text.lower()

            if awaiting_command:
                # já ouvimos "Mendes" antes; esta fala É o comando.
                awaiting_command = False
                await _emit_command(bus, state, text)
            elif wake in low:
                idx = low.rfind(wake)
                comando = text[idx + len(wake):].strip(" ,.!?:;")
                if comando:
                    await _emit_command(bus, state, comando)
                else:
                    awaiting_command = True  # disse só "Mendes" -> espera o comando
                    state.push_event("ativado", {"assistente": settings.assistant_name})
            # sem a palavra de ativação -> ignora (não age)
    except asyncio.CancelledError:
        raise
    finally:
        state.listening = False


async def _emit_command(bus: EventBus, state, comando: str) -> None:
    log.info("comando de voz: %s", comando)
    state.push_event("comando", {"texto": comando})
    await bus.publish(events.speech_final(comando))
