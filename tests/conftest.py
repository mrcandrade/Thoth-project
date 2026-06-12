"""Fixtures de teste: uma mão falsa (sem hardware) e config de teste."""
from __future__ import annotations

import pytest


class FakeHand:
    """Implementa a interface usada pelas primitivas, registrando as chamadas."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def gesture(self, name: str) -> str:
        self.calls.append(("gesture", name))
        return f"A:P:{name}"

    async def set_angles(self, thumb: int, index: int, other: int) -> str:
        self.calls.append(("set_angles", thumb, index, other))
        return "A:G"

    async def stop(self) -> str:
        self.calls.append(("stop",))
        return "A:S"


@pytest.fixture
def fake_hand() -> FakeHand:
    return FakeHand()
