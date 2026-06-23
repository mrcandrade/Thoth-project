"""Ouvido do agente — captura do microfone com detecção de fim de turno (VAD).

Grava um trecho de fala: espera você começar a falar, captura até detectar
~silêncio (fim do turno) e devolve o áudio como WAV (16 kHz mono) pronto p/ STT.
"""
from __future__ import annotations

import io
import logging
import wave

log = logging.getLogger("thoth.listen")

SR = 16_000          # 16 kHz (Whisper/webrtcvad)
FRAME_MS = 30        # webrtcvad aceita 10/20/30 ms
FRAME = SR * FRAME_MS // 1000   # 480 amostras = 960 bytes (int16)


def _resolve_device(mic_device: str | None):
    if not mic_device:
        return None
    return int(mic_device) if str(mic_device).isdigit() else mic_device


class Listener:
    def __init__(self, mic_device: str | None = None, aggressiveness: int = 2,
                 silence_ms: int = 700, max_ms: int = 15_000, start_ms: int = 150):
        import webrtcvad  # import adiado

        self.vad = webrtcvad.Vad(aggressiveness)   # 0..3 (3 = mais agressivo)
        self.device = _resolve_device(mic_device)
        self.silence_frames = max(1, silence_ms // FRAME_MS)
        self.max_frames = max_ms // FRAME_MS
        self.start_frames = max(1, start_ms // FRAME_MS)

    def listen(self) -> bytes | None:
        """Bloqueia até captar uma fala completa. Retorna WAV (bytes) ou None."""
        import sounddevice as sd

        voiced: list[bytes] = []
        triggered = False
        consecutive_voice = 0
        silence = 0

        with sd.RawInputStream(samplerate=SR, blocksize=FRAME, dtype="int16",
                               channels=1, device=self.device) as stream:
            for _ in range(self.max_frames):
                data, _overflow = stream.read(FRAME)
                frame = bytes(data)
                if len(frame) < FRAME * 2:
                    continue
                speech = self.vad.is_speech(frame, SR)

                if not triggered:
                    if speech:
                        consecutive_voice += 1
                        voiced.append(frame)
                        if consecutive_voice >= self.start_frames:
                            triggered = True
                    else:
                        consecutive_voice = 0
                        voiced.clear()
                else:
                    voiced.append(frame)
                    if speech:
                        silence = 0
                    else:
                        silence += 1
                        if silence >= self.silence_frames:
                            break

        if not triggered or not voiced:
            return None
        return _pcm_to_wav(b"".join(voiced))


def _pcm_to_wav(pcm: bytes, sr: int = SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm)
    return buf.getvalue()
