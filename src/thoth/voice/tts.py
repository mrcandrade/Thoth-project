"""Síntese de voz (TTS) do Mendes via pyttsx3 (SAPI5 no Windows).

Offline, sem custo de API, usa a SAÍDA DE ÁUDIO PADRÃO do sistema. O engine do
pyttsx3 não é thread-safe e o ``runAndWait()`` bloqueia, então rodamos o engine
em uma thread dedicada alimentada por uma fila. ``say()`` apenas enfileira.
"""
from __future__ import annotations

import logging
import queue
import threading

log = logging.getLogger("thoth.tts")


class Speaker:
    def __init__(self, rate: int = 180, voice_hint: str = "brazil", enabled: bool = True):
        self.enabled = enabled
        self._rate = rate
        self._voice_hint = voice_hint.lower()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        if enabled:
            self._thread = threading.Thread(target=self._run, daemon=True, name="tts")
            self._thread.start()

    def _run(self) -> None:
        try:
            import pyttsx3
        except ImportError:
            log.warning("pyttsx3 não instalado — voz desativada.")
            return

        engine = pyttsx3.init()  # SAPI5 no Windows
        engine.setProperty("rate", self._rate)
        # tenta selecionar uma voz PT-BR pelo trecho informado
        try:
            for v in engine.getProperty("voices"):
                blob = f"{v.name} {getattr(v, 'id', '')} {getattr(v, 'languages', '')}".lower()
                if self._voice_hint and self._voice_hint in blob:
                    engine.setProperty("voice", v.id)
                    log.info("voz TTS selecionada: %s", v.name)
                    break
        except Exception:  # noqa: BLE001
            pass

        while True:
            text = self._queue.get()
            if text is None:  # sinal de parada
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as exc:  # noqa: BLE001
                log.warning("falha no TTS: %s", exc)

    def say(self, text: str) -> None:
        """Enfileira uma fala (não bloqueia)."""
        if self.enabled and text:
            self._queue.put(text)

    def stop(self) -> None:
        if self.enabled:
            self._queue.put(None)
