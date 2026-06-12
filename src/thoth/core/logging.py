"""Configuração de logging. Usa loguru se disponível; senão, stdlib logging.

Mantemos um fallback para a stdlib para que importar o pacote não exija o
loguru instalado (útil em testes e ambientes mínimos).
"""
from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configura o logging do processo. Idempotente."""
    try:
        from loguru import logger  # type: ignore

        logger.remove()
        logger.add(
            sys.stderr,
            level=level.upper(),
            format=(
                "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
                "<cyan>{name}</cyan> - <level>{message}</level>"
            ),
        )

        # Redireciona o logging da stdlib para o loguru.
        class _InterceptHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
                try:
                    lvl = logger.level(record.levelname).name
                except ValueError:
                    lvl = record.levelno
                logger.opt(depth=6, exception=record.exc_info).log(lvl, record.getMessage())

        logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    except ImportError:
        logging.basicConfig(
            level=level.upper(),
            format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
            datefmt="%H:%M:%S",
        )
