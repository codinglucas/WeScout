"""Typed records that providers return and the repository stores.

Providers only translate their payloads into these records; they never touch the DB.
All IDs here are the provider's own IDs (strings), never internal IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

License = Literal["licensed", "local_scrape"]
CoarsePosition = Literal["GK", "DF", "MF", "FW"]
FeeType = Literal["fee", "loan", "loan_end", "free", "unknown"]

# Frontend position codes -> coarse group. Used for search fallback when only
# a coarse position is known (API-Football season stats).
DETAILED_TO_COARSE: dict[str, CoarsePosition] = {
    "gk": "GK",
    "sweeper": "DF",
    "cb": "DF",
    "lb": "DF",
    "rb": "DF",
    "cdm": "MF",
    "cm": "MF",
    "rm": "MF",
    "lm": "MF",
    "cam": "MF",
    "lw": "FW",
    "rw": "FW",
    "st": "FW",
    "cf": "FW",
}


@dataclass(frozen=True)
class SearchFilters:
    min_age: int | None = None
    max_age: int | None = None
    min_value: int | None = None
    max_value: int | None = None
    position: str | None = None  # frontend code, e.g. "lb"
    competition_ids: tuple[str, ...] = ()
    season: int | None = None


@dataclass(frozen=True)
class ClubRef:
    source_id: str
    name: str
    country: str | None = None


@dataclass(frozen=True)
class CompetitionRef:
    source_id: str
    name: str
    country: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class PlayerRecord:
    source: str
    source_player_id: str
    name: str
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    foot: str | None = None
    position: CoarsePosition | None = None
    detailed_position: str | None = None
    photo_url: str | None = None


@dataclass(frozen=True)
class SeasonStatsRecord:
    source: str
    source_player_id: str
    competition: CompetitionRef
    club: ClubRef
    season_start_year: int
    position: CoarsePosition | None = None
    appearances: int | None = None
    starts: int | None = None
    minutes: int | None = None
    rating: float | None = None
    goals: int | None = None
    assists: int | None = None
    key_passes: int | None = None
    tackles: int | None = None
    interceptions: int | None = None
    dribbled_past: int | None = None
    big_chances_created: int | None = None
    accurate_passes: int | None = None
    total_passes: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketValueRecord:
    source: str
    source_player_id: str
    valued_at: date
    value_eur: int
    club: ClubRef | None = None


@dataclass(frozen=True)
class TransferRecord:
    source: str
    source_player_id: str
    transfer_date: date | None
    from_club: ClubRef | None
    to_club: ClubRef | None
    fee_eur: int | None = None
    fee_type: FeeType = "unknown"
    fee_raw: str | None = None

    @property
    def transfer_key(self) -> str:
        d = self.transfer_date.isoformat() if self.transfer_date else "?"
        f = self.from_club.source_id if self.from_club else "?"
        t = self.to_club.source_id if self.to_club else "?"
        return f"{d}|{f}|{t}"


@dataclass(frozen=True)
class ContractRecord:
    source: str
    source_player_id: str
    club: ClubRef
    expires: date | None
    observed_at: date


@dataclass(frozen=True)
class FetchResult:
    """What a provider call returns: records plus how many network requests it cost."""

    players: list[PlayerRecord] = field(default_factory=list)
    stats: list[SeasonStatsRecord] = field(default_factory=list)
    market_values: list[MarketValueRecord] = field(default_factory=list)
    transfers: list[TransferRecord] = field(default_factory=list)
    requests_made: int = 0
    total_pages: int | None = None
    fetched_at: datetime | None = None
