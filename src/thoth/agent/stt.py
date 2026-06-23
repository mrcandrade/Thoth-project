"""Transcrição de fala (STT) — Groq Whisper (nuvem) ou faster-whisper (local)."""
from __future__ import annotations

import io
import logging

from thoth.core.config import Settings

log = logging.getLogger("thoth.stt")


class STT:
    def __init__(self, settings: Settings):
        self.s = settings
        self._groq = None
        self._fw = None

    def transcribe(self, audio_bytes: bytes, filename: str = "speech.wav") -> str:
        """Transcreve áudio. ``filename`` indica o container (a nuvem detecta o
        formato pela extensão): WAV no terminal, webm/ogg vindo do navegador."""
        if (self.s.stt_provider or "groq").lower() == "local":
            return self._local(audio_bytes)
        return self._groq_whisper(audio_bytes, filename)

    # --- Groq Whisper (nuvem, via cliente OpenAI-compatible) ---
    def _groq_whisper(self, audio_bytes: bytes, filename: str = "speech.wav") -> str:
        if self._groq is None:
            from openai import OpenAI

            self._groq = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.s.groq_api_key or "EMPTY",
            )
        resp = self._groq.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=self.s.stt_model,
            language="pt",
            response_format="text",
        )
        text = resp if isinstance(resp, str) else getattr(resp, "text", "")
        return (text or "").strip()

    # --- faster-whisper (local, offline; decodifica via ffmpeg/PyAV) ---
    def _local(self, audio_bytes: bytes) -> str:
        if self._fw is None:
            from faster_whisper import WhisperModel

            self._fw = WhisperModel("small", device="cpu", compute_type="int8")
        segments, _info = self._fw.transcribe(io.BytesIO(audio_bytes), language="pt")
        return " ".join(seg.text for seg in segments).strip()
