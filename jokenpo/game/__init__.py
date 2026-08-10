"""Pacote do jogo Jokenpô Robótico.

Camada que implementa a lógica do jogo e integra com o projeto Thoth (mão
HACKberry via serial, webcam + visão computacional, TTS). É consumida pelos
steps do workflow Agno (``workflow_jokenpo_robotico.py``) e pelo servidor web.

Este módulo garante que o pacote ``thoth`` (do ``src/`` do projeto pai) seja
importável mesmo sem ``pip install -e ..``: se o import falhar, adiciona
``../src`` ao ``sys.path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# jokenpo/game/__init__.py -> parents[2] = raiz do Thoth-project
_THOTH_SRC = Path(__file__).resolve().parents[2] / "src"
if _THOTH_SRC.is_dir():
    try:
        import thoth  # noqa: F401  (só testa se já é importável)
    except ImportError:
        sys.path.insert(0, str(_THOTH_SRC))
