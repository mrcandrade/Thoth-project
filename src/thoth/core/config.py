"""Configuração central (única fonte de verdade) da entrega web.

Apenas este módulo lê `.env` / ambiente; o resto recebe um ``Settings`` por
injeção. Carrega `.env` (pydantic-settings) + overrides de `configs/<env>.yaml`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório (…/src/thoth/core/config.py -> sobe 3 níveis)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_DIR = PROJECT_ROOT / "configs"


class Settings(BaseSettings):
    """Configuração tipada da entrega web (mão HACKberry + visão)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Hardware / serial (Arduino) ---
    serial_port: str = "COM19"     # FTDI Boarduino (a porta pode variar; confirme com check_devices.py)
    serial_baud: int = 115200
    serial_heartbeat_ms: int = 300

    # --- Câmera (visão computacional) ---
    camera_index: int = 1          # Logitech (confirme com scripts/check_devices.py)
    camera_width: int = 1280
    camera_height: int = 720

    # --- App / API ---
    thoth_env: str = "dev"         # dev | prod (seleciona configs/<env>.yaml)
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    # --- Agente conversacional (Fase 1: voz) ---
    assistant_name: str = "Marco"
    # Cérebro (LLM): endpoint OpenAI-compatible, PLUGÁVEL.
    # provider = cerebras | groq | custom. Para o Rio-3.5-397B, use provider=custom
    # + llm_base_url do seu endpoint vLLM (OpenAI-compatible) + llm_model.
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-120b"  # id no provedor (fiel a ferramentas)
    llm_base_url: str | None = None         # override (ex.: http://SEU_VLLM:8000/v1)
    cerebras_api_key: str | None = None
    groq_api_key: str | None = None
    # Visão (VLM multimodal): usado pelas skills de visão (ver_cena, ler_texto, jokenpô)
    vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    # Cidade padrão p/ a skill de clima quando o usuário não disser
    default_city: str = "Porto Alegre"
    # Ouvido (STT): groq (Whisper na nuvem) | local (faster-whisper)
    stt_provider: str = "groq"
    stt_model: str = "whisper-large-v3"
    # Voz (TTS): edge (online, neural, PT-BR) | piper (offline, fallback)
    tts_provider: str = "edge"
    edge_voice: str = "pt-BR-ThalitaMultilingualNeural"  # neural; alt: AntonioNeural/FranciscaNeural
    edge_rate: str = "+0%"                  # velocidade da fala (ex.: "+10%", "-5%")
    edge_pitch: str = "+0Hz"               # tom da fala (ex.: "+20Hz", "-10Hz")
    piper_voice: str = "pt_BR-faber-medium"  # usado só com tts_provider=piper
    mic_device: str | None = None           # vazio = microfone padrão do Windows

    # Overrides declarativos de configs/<env>.yaml (não vêm do .env).
    extra_yaml: dict = Field(default_factory=dict)

    @field_validator(
        "llm_base_url", "mic_device", "cerebras_api_key", "groq_api_key", mode="before"
    )
    @classmethod
    def _blank_or_comment_to_none(cls, v):
        """Trata valor vazio ou comentário inline (# ...) no .env como None.

        Evita que uma linha tipo `MIC_DEVICE=   # comentário` seja lida com o
        comentário como valor.
        """
        if v is None:
            return None
        s = str(v).strip()
        return None if (s == "" or s.startswith("#")) else s

    @property
    def heartbeat_period(self) -> float:
        """Período de heartbeat em segundos (para o HandLink)."""
        return self.serial_heartbeat_ms / 1000.0


def _load_yaml_overrides(env: str) -> dict:
    path = CONFIGS_DIR / f"{env}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a configuração (cacheada). Mescla `.env` + configs/<env>.yaml."""
    settings = Settings()
    overrides = _load_yaml_overrides(settings.thoth_env)
    if overrides:
        settings.extra_yaml = overrides
    return settings
