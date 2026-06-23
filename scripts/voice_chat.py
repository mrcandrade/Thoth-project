"""Conversa por voz com o Marco (Fase 1 do agente) — escutar, pensar, falar.

Pré-requisitos:
  - .env com LLM_PROVIDER + a chave (CEREBRAS_API_KEY ou GROQ_API_KEY) e GROQ_API_KEY (STT)
  - voz do Piper baixada:  python scripts/download_piper.py
  - microfone e alto-falante

Uso:  python scripts/voice_chat.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar sem `pip install -e .` (adiciona src/ ao path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thoth.agent.chat import run  # noqa: E402

if __name__ == "__main__":
    run()
