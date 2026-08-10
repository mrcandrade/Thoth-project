"""Configuração do jogo: reaproveita o ``Settings`` do Thoth + opções do jogo.

O ``.env`` de hardware/voz fica em ``jokenpo/.env`` (mesmo diretório de onde se
roda o ``orquestrador.py``). Aqui carregamos esse ``.env`` ANTES de instanciar o
``Settings`` do Thoth, para que porta serial, câmera, TTS e visão venham dele.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Carrega jokenpo/.env -> os.environ (o Settings do Thoth lê de os.environ).
_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV, override=False)


@lru_cache(maxsize=1)
def settings():
    """Devolve o ``Settings`` do Thoth (porta serial, câmera, TTS, visão…)."""
    from thoth.core.config import get_settings

    return get_settings()


# --- Opções específicas do jogo (via env, com defaults sensatos) -----------
# Tocar a narração TAMBÉM no alto-falante do servidor (além do navegador).
SERVER_AUDIO = os.getenv("GAME_SERVER_AUDIO", "0") == "1"
# Usar o VLM da Anthropic (Claude) como reforço quando o MediaPipe ficar em dúvida.
USE_VLM_FALLBACK = os.getenv("GAME_VLM_FALLBACK", "1") != "0"
# Janela (s) de votação de gestos ao "já" da contagem.
SAMPLE_WINDOW_S = float(os.getenv("GAME_SAMPLE_WINDOW_S", "0.7"))
# Modelo de visão da Anthropic (default = mesmo modelo dos agentes).
VLM_MODEL = os.getenv("ANTHROPIC_VISION_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"))
