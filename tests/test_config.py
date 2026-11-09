from __future__ import annotations

import pytest

from wescout.config import load_settings


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("PUBLIC_MODE", "ENABLE_LOCAL_SCRAPERS", "API_FOOTBALL_KEY"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings(env_file=None)
    assert s.public_mode is True
    assert s.enable_local_scrapers is False
    assert s.api_football_key is None


def test_flags_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_MODE", "false")
    monkeypatch.setenv("ENABLE_LOCAL_SCRAPERS", "TRUE")
    s = load_settings(env_file=None)
    assert s.public_mode is False
    assert s.enable_local_scrapers is True
