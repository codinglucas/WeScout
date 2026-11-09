from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never hit the network: any socket connect fails loudly."""

    def guard(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Network access attempted in tests; use recorded fixtures.")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


@pytest.fixture
def load_fixture() -> Any:
    def _load(name: str) -> Any:
        path = FIXTURES / name
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8")

    return _load
