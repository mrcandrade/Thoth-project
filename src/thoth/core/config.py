"""Configuração central (única fonte de verdade).

Apenas este módulo lê variáveis de ambiente / `.env`. Todos os demais módulos
recebem um objeto ``Settings`` por injeção (nunca acessam ``os.environ``),
o que torna os testes determinísticos.

Carga: `.env` (via pydantic-settings) sobreposto por `configs/<THOTH_ENV>.yaml`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório (…/src/thoth/core/config.py -> sobe 3 níveis)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_DIR = PROJECT_ROOT / "configs"


class Settings(BaseSettings):
    """Configuração tipada do Thoth, lida de `.env` + ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        protected_namespaces=(),  # permite campos começando com "model_"
    )

    # --- Provedores de IA (opcionais p/ permitir importar/testar sem chaves) ---
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None

    # --- Modelos por papel ---
    model_planner: str = Field("claude-opus-4-8", alias="THOTH_MODEL_PLANNER")
    model_conversation: str = Field("claude-sonnet-4-6", alias="THOTH_MODEL_CONVERSATION")
    model_vision: str = Field(
        "meta-llama/llama-4-scout-17b-16e-instruct", alias="THOTH_MODEL_VISION"
    )
    model_stt: str = Field("whisper-large-v3", alias="THOTH_MODEL_STT")
    model_fast: str = Field("gpt-oss-120b", alias="THOTH_MODEL_FAST")

    # --- Hardware / serial ---
    serial_port: str = "COM5"
    serial_baud: int = 115200
    serial_heartbeat_ms: int = 300
    estop_gpio_pin: int | None = None

    # --- Identidade do assistente ---
    assistant_name: str = "Mendes"
    # wake_mode: "phrase" = escuta contínua + detecta a palavra na transcrição (STT);
    #            "openwakeword" = modelo de wake word dedicado (exige modelo treinado).
    wake_mode: str = "phrase"
    wake_word: str = "mendes"

    # --- Percepção ---
    camera_index: int = 0          # índice da Logitech (descubra com scripts/check_devices.py)
    camera_width: int = 1280
    camera_height: int = 720
    mic_device: str | None = None  # vazio = microfone PADRÃO do Windows
    wakeword_model: str = "hey_jarvis"  # usado só no modo "openwakeword"
    face_match_threshold: float = 0.45

    # --- Saída de voz (TTS) ---
    tts_enabled: bool = True
    tts_rate: int = 180            # palavras/min (pyttsx3)
    tts_voice_hint: str = "brazil"  # trecho do nome/idioma da voz SAPI a preferir (ex.: "pt", "brazil", "maria")
    audio_output_device: str | None = None  # vazio = saída PADRÃO do notebook

    # --- Caminhos de artefatos ---
    mediapipe_models_dir: str = "./models/mediapipe"
    face_gallery_path: str = "./data/encodings.pkl"
    known_faces_dir: str = "./data/known_faces"

    # --- App / API ---
    thoth_env: str = Field("dev", alias="THOTH_ENV")
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    # Overrides declarativos carregados de configs/<env>.yaml (não vêm do .env).
    extra_yaml: dict = Field(default_factory=dict)

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
