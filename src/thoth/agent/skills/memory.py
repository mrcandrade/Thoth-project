"""Memória de longo prazo do agente: nome e preferências do usuário.

Persiste num JSON em data/agent_memory.json. É carregada no início da conversa
(injetada no system prompt) e atualizada pela skill ``lembrar``.
"""
from __future__ import annotations

import json
import logging

from thoth.core.config import PROJECT_ROOT

log = logging.getLogger("thoth.skills.memory")

_FILE = PROJECT_ROOT / "data" / "agent_memory.json"


def _load() -> dict:
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        data.setdefault("user_name", None)
        data.setdefault("facts", [])
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"user_name": None, "facts": []}


def _save(data: dict) -> None:
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("não consegui salvar a memória: %s", exc)


def set_user_name(name: str) -> None:
    data = _load()
    data["user_name"] = name.strip()
    _save(data)


def add_fact(fact: str) -> None:
    data = _load()
    fact = fact.strip()
    if fact and fact not in data["facts"]:
        data["facts"].append(fact)
        _save(data)


def memory_summary() -> str:
    """Resumo em texto da memória, para injetar no system prompt (vazio se nada)."""
    data = _load()
    partes: list[str] = []
    if data.get("user_name"):
        partes.append(f"O nome do usuário é {data['user_name']}.")
    if data.get("facts"):
        partes.append("Você também sabe: " + " ".join(f"{f}." for f in data["facts"]))
    return " ".join(partes)
