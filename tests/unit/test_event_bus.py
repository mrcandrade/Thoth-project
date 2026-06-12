"""Testes do EventBus assíncrono (pub/sub + prioridade)."""
from __future__ import annotations

import asyncio

from thoth.core.event_bus import Event, EventBus, Priority


async def test_pub_sub_entrega_evento():
    bus = EventBus()
    recebidos: list[str] = []

    async def handler(ev: Event) -> None:
        recebidos.append(ev.payload["msg"])

    bus.subscribe("ping", handler)
    bus.start()
    await bus.emit("ping", {"msg": "ola"})
    await asyncio.sleep(0.05)
    assert recebidos == ["ola"]
    await bus.stop()


async def test_wildcard_recebe_tudo():
    bus = EventBus()
    todos: list[str] = []

    async def espiao(ev: Event) -> None:
        todos.append(ev.type)

    bus.subscribe("*", espiao)
    bus.start()
    await bus.emit("a")
    await bus.emit("b")
    await asyncio.sleep(0.05)
    assert set(todos) == {"a", "b"}
    await bus.stop()


async def test_prioridade_critica_sai_primeiro():
    bus = EventBus()
    ordem: list[str] = []

    async def handler(ev: Event) -> None:
        ordem.append(ev.type)

    bus.subscribe("normal", handler)
    bus.subscribe("estop", handler)
    # enfileira ANTES de iniciar o dispatch, para a fila ordenar por prioridade
    await bus.publish(Event("normal", priority=Priority.NORMAL))
    await bus.publish(Event("estop", priority=Priority.CRITICAL))
    bus.start()
    await asyncio.sleep(0.05)
    assert ordem[0] == "estop"
    await bus.stop()
