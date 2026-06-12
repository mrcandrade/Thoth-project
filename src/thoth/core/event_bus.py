"""EventBus assíncrono (pub/sub) para coordenação entre módulos do Thoth.

É o ponto de desacoplamento entre os produtores (Visão, Voz) e os consumidores
(Orquestrador, demais agentes). Sobre asyncio, com prioridade de eventos
(parada de emergência = CRITICAL sai primeiro).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3  # ex.: parada de emergência


@dataclass(order=True)
class Event:
    # 'order=True' + sort_index permite usar em PriorityQueue (maior prioridade primeiro)
    sort_index: float = field(init=False, repr=False)
    type: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
    priority: Priority = field(default=Priority.NORMAL, compare=False)
    timestamp: float = field(default_factory=time.time, compare=False)

    def __post_init__(self) -> None:
        # negativo: prioridade alta sai primeiro; desempate por timestamp (mais antigo primeiro)
        self.sort_index = -float(self.priority) * 1e12 + self.timestamp


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._queue: asyncio.PriorityQueue[Event] = asyncio.PriorityQueue()
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Inscreve um handler. Use '*' para receber todos os eventos."""
        self._subs[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    async def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        priority: Priority = Priority.NORMAL,
    ) -> None:
        """Atalho de publicação."""
        await self.publish(Event(type=type, payload=payload or {}, priority=priority))

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._dispatch_loop(), name="eventbus")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _dispatch_loop(self) -> None:
        while True:
            event = await self._queue.get()
            handlers = self._subs.get(event.type, []) + self._subs.get("*", [])
            # executa handlers concorrentemente; um erro não derruba os demais
            await asyncio.gather(
                *(self._safe(h, event) for h in handlers),
                return_exceptions=True,
            )

    @staticmethod
    async def _safe(handler: Handler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("thoth.bus").exception("handler falhou: %s", exc)
