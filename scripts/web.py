"""Sobe APENAS o painel web de controle da mão (sem agentes de IA).

Conecta na porta serial do .env (SERIAL_PORT) e serve o dashboard em
http://127.0.0.1:8000 — botões de gesto + sliders por dedo + e-stop.

Uso:  python scripts/web.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar sem `pip install -e .` (adiciona src/ ao path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn  # noqa: E402

from thoth.api.server import app  # noqa: E402
from thoth.core.config import get_settings  # noqa: E402

if __name__ == "__main__":
    s = get_settings()
    print(f"Painel: http://{s.api_host}:{s.api_port}   (mão em {s.serial_port})")
    uvicorn.run(app, host=s.api_host, port=s.api_port, log_level="info")
