"""Configuração central (única fonte de verdade) da entrega web.

Apenas este módulo lê `.env` / ambiente; o resto recebe um ``Settings`` por
injeção. Carrega `.env` (pydantic-settings) + overrides de `configs/<env>.yaml`.
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
    """Configuração tipada da entrega web (mão HACKberry + visão)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Hardware / serial (Arduino) ---
    serial_port: str = "COM17"
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

    # Overrides declarativos de configs/<env>.yaml (não vêm do .env).
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
