"""The provider contract. Every data source (licensed API or local scraper) implements it."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from wescout.models import (
    FetchResult,
    License,
    MarketValueRecord,
    PlayerRecord,
    SearchFilters,
    SeasonStatsRecord,
)


class ProviderError(RuntimeError):
    """The provider answered, but with an error we can't recover from."""


class ProviderBlocked(ProviderError):
    """The site refused us (403/challenge). We stop - we never try to get around it."""


class QuotaExhausted(ProviderError):
    """Daily request budget reached (including the configured reserve)."""


@runtime_checkable
class Provider(Protocol):
    name: str
    license: License
    attribution: str | None

    def search_players(self, filters: SearchFilters) -> FetchResult: ...

    def get_player(self, player_id: str) -> PlayerRecord | None: ...

    def get_season_stats(self, player_id: str, season: int) -> list[SeasonStatsRecord]: ...

    def get_market_values(self, player_id: str) -> list[MarketValueRecord]: ...
