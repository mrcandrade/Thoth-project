"""Voz do agente (TTS) — PLUGÁVEL: edge-tts (online, neural) ou Piper (offline).

- ``edge`` (padrão): vozes neurais PT-BR da Microsoft (edge-tts), gratuitas e sem
  chave, muito mais naturais. Requer internet. Voz em EDGE_VOICE.
- ``piper`` (fallback offline): executável Piper local (modelo em models/piper/).

Ambos expõem a mesma interface ``.say(text)`` (bloqueante). Escolha em TTS_PROVIDER.
A fábrica ``make_tts(settings)`` devolve o motor certo (com fallback p/ Piper se o
edge-tts não estiver instalável).
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from thoth.core.config import PROJECT_ROOT, Settings

log = logging.getLogger("thoth.tts")

# Serializa o acesso ao dispositivo de áudio: o loop principal e a thread do
# lembrete (threading.Timer) podem chamar say() ao mesmo tempo — sem isto,
# sd.play()/sd.wait() concorreriam pelo mesmo device.
_audio_lock = threading.Lock()


def _play(audio_path: str) -> None:
    """Reproduz um arquivo de áudio (WAV/MP3) pelo alto-falante padrão (bloqueante)."""
    import sounddevice as sd
    import soundfile as sf

    data, sr = sf.read(audio_path, dtype="float32")
    with _audio_lock:
        sd.play(data, sr)
        sd.wait()


def _play_bytes(data: bytes, suffix: str) -> None:
    """Toca bytes de áudio (escreve num temporário e reproduz)."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    try:
        _play(tmp.name)
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


class EdgeTTS:
    """TTS neural online (Microsoft Edge), PT-BR — gratuito, sem chave, natural."""

    def __init__(self, settings: Settings):
        import edge_tts  # import adiado: valida instalação só quando usado

        self._edge_tts = edge_tts
        self.voice = settings.edge_voice
        self.rate = settings.edge_rate
        self.pitch = settings.edge_pitch
        log.info("Voz: edge-tts %s (rate=%s, pitch=%s)", self.voice, self.rate, self.pitch)

    def synth_bytes(self, text: str) -> bytes | None:
        """Sintetiza e devolve o áudio MP3 em bytes (sem tocar). Usado pela web."""
        text = (text or "").strip()
        if not text:
            return None
        comm = self._edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
        buf = bytearray()

        async def _collect() -> None:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])

        asyncio.run(_collect())
        return bytes(buf) or None

    def say(self, text: str) -> None:
        try:
            data = self.synth_bytes(text)
        except Exception as exc:  # noqa: BLE001  (rede instável não pode derrubar o loop)
            log.warning("edge-tts falhou (%s): %s", type(exc).__name__, str(exc)[:200])
            return
        if data:
            _play_bytes(data, ".mp3")


class Piper:
    """TTS local offline (executável Piper). Fallback sem internet."""

    def __init__(self, settings: Settings):
        self.model = PROJECT_ROOT / "models" / "piper" / f"{settings.piper_voice}.onnx"
        exe = shutil.which("piper")
        self.cmd_prefix = [exe] if exe else [sys.executable, "-m", "piper"]
        if not self.model.exists():
            raise FileNotFoundError(
                f"voz Piper não encontrada: {self.model} "
                "(rode: python scripts/download_piper.py)"
            )
        log.info("Voz: Piper %s", self.model.name)

    def synth_bytes(self, text: str) -> bytes | None:
        """Sintetiza e devolve o áudio WAV em bytes (sem tocar). Usado pela web."""
        text = (text or "").strip()
        if not text:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            subprocess.run(
                [*self.cmd_prefix, "-m", str(self.model), "-f", tmp.name],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
            with open(tmp.name, "rb") as f:
                return f.read() or None
        except subprocess.CalledProcessError as exc:
            log.warning("piper falhou: %s", exc.stderr.decode(errors="replace")[:200])
            return None
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    def say(self, text: str) -> None:
        data = self.synth_bytes(text)
        if data:
            _play_bytes(data, ".wav")


def make_tts(settings: Settings):
    """Devolve o motor de TTS conforme TTS_PROVIDER (com fallback p/ Piper)."""
    provider = (settings.tts_provider or "edge").lower()
    if provider == "piper":
        return Piper(settings)
    try:
        return EdgeTTS(settings)
    except ImportError:
        log.warning("edge-tts não instalado (pip install edge-tts); usando Piper.")
        return Piper(settings)
