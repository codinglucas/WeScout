"""API-Football v3 (api-sports.io) - the licensed provider.

Checked against the live API on 2026-11-09 (see docs/benchmarks.md):
  * free plan: 100 requests/day, 10/minute; seasons 2022-2024 only
  * /players?league&season is paginated, 20 players per page (~50 pages per league-season)
  * errors come back as HTTP 200 with a non-empty `errors` field
  * no market values; transfer fees are free text in `type` ("€ 17.5M", "Loan", ...)
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from wescout.models import (
    ClubRef,
    CoarsePosition,
    CompetitionRef,
    FeeType,
    FetchResult,
    MarketValueRecord,
    PlayerRecord,
    SearchFilters,
    SeasonStatsRecord,
    TransferRecord,
)
from wescout.providers.base import ProviderError, QuotaExhausted
from wescout.providers.http import HttpClient, QuotaTracker

SOURCE = "api_football"
BASE_URL = "https://v3.football.api-sports.io"
FREE_PLAN_SEASONS = range(2022, 2025)

_POSITIONS: dict[str, CoarsePosition] = {
    "Goalkeeper": "GK",
    "Defender": "DF",
    "Midfielder": "MF",
    "Attacker": "FW",
}


# ---------------------------------------------------------------- small parsers


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else None


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


_AMOUNT = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>[mMkK])?")


def parse_fee(raw: str | None) -> tuple[int | None, FeeType]:
    """Turn API-Football's free-text transfer `type` into (fee_eur, fee_type).

    Non-euro amounts (e.g. '£ 1.5M') are kept as fee_type='fee' with fee_eur=None: converting
    needs an exchange rate at the transfer date, which we don't have. fee_raw keeps the text.
    """
    if raw is None:
        return None, "unknown"
    text = html.unescape(raw).strip()
    low = text.lower()
    if low in {"", "-", "n/a", "transfer", "raise", "?"}:
        return None, "unknown"
    if "back from loan" in low or "return from loan" in low or "end of loan" in low:
        return None, "loan_end"
    if "loan" in low:
        return None, "loan"
    if "free" in low:
        return 0, "free"
    m = _AMOUNT.search(text)
    if not m:
        return None, "unknown"
    if "€" not in text and "eur" not in low:
        return None, "fee"
    amount = float(m.group("num").replace(",", "."))
    unit = (m.group("unit") or "").lower()
    amount *= {"m": 1_000_000, "k": 1_000}.get(unit, 1)
    return round(amount), "fee"


# ---------------------------------------------------------------- payload -> records


def parse_player(item: dict[str, Any], position: CoarsePosition | None = None) -> PlayerRecord:
    p = item["player"]
    birth = p.get("birth") or {}
    return PlayerRecord(
        source=SOURCE,
        source_player_id=str(p["id"]),
        name=p.get("name") or f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
        first_name=p.get("firstname"),
        last_name=p.get("lastname"),
        date_of_birth=_date(birth.get("date")),
        nationality=p.get("nationality"),
        height_cm=_int(p.get("height")),
        weight_kg=_int(p.get("weight")),
        position=position,
        photo_url=p.get("photo"),
    )


def parse_stats(
    item: dict[str, Any], season: int, league_id: int | None = None
) -> list[SeasonStatsRecord]:
    """One record per (club, competition) entry that has any playing time."""
    player_id = str(item["player"]["id"])
    out: list[SeasonStatsRecord] = []
    for s in item.get("statistics", []):
        league, team, games = s["league"], s["team"], s.get("games") or {}
        if league_id is not None and league.get("id") != league_id:
            continue
        appearances = _int(games.get("appearences"))  # sic: API spelling
        minutes = _int(games.get("minutes"))
        if not appearances and not minutes:
            continue
        passes, tackles = s.get("passes") or {}, s.get("tackles") or {}
        goals, dribbles = s.get("goals") or {}, s.get("dribbles") or {}
        out.append(
            SeasonStatsRecord(
                source=SOURCE,
                source_player_id=player_id,
                competition=CompetitionRef(
                    str(league["id"]), league["name"], league.get("country"), "league"
                ),
                club=ClubRef(str(team["id"]), team["name"]),
                season_start_year=season,
                position=_POSITIONS.get(games.get("position") or ""),
                appearances=appearances,
                starts=_int(games.get("lineups")),
                minutes=minutes,
                rating=_float(games.get("rating")),
                goals=_int(goals.get("total")),
                assists=_int(goals.get("assists")),
                key_passes=_int(passes.get("key")),
                tackles=_int(tackles.get("total")),
                interceptions=_int(tackles.get("interceptions")),
                dribbled_past=_int(dribbles.get("past")),
                big_chances_created=None,  # not provided by API-Football
                # passes.accuracy is ambiguous at season level (neither a % nor a total
                # we can verify), so it goes to `extra` instead of accurate_passes.
                accurate_passes=None,
                total_passes=_int(passes.get("total")),
                extra={
                    "passes_accuracy_raw": passes.get("accuracy"),
                    "shots": s.get("shots"),
                    "duels": s.get("duels"),
                    "dribbles": {k: dribbles.get(k) for k in ("attempts", "success")},
                    "tackles_blocks": tackles.get("blocks"),
                    "fouls": s.get("fouls"),
                    "cards": s.get("cards"),
                    "substitutes": s.get("substitutes"),
                    "goals_conceded": goals.get("conceded"),
                    "saves": goals.get("saves"),
                    "penalty": s.get("penalty"),
                    "captain": games.get("captain"),
                },
            )
        )
    return out


def parse_players_page(
    payload: dict[str, Any], season: int, league_id: int | None = None
) -> FetchResult:
    players: list[PlayerRecord] = []
    stats: list[SeasonStatsRecord] = []
    for item in payload.get("response", []):
        rows = parse_stats(item, season, league_id)
        # Coarse position from the entry with the most minutes.
        main = max(rows, key=lambda r: r.minutes or 0, default=None)
        position = main.position if main else None
        if position is None:  # unused squad players still have a registered position
            for s in item.get("statistics", []):
                position = _POSITIONS.get((s.get("games") or {}).get("position") or "")
                if position:
                    break
        players.append(parse_player(item, position))
        stats.extend(rows)
    paging = payload.get("paging") or {}
    return FetchResult(players=players, stats=stats, total_pages=_int(paging.get("total")))


def parse_transfers(payload: dict[str, Any]) -> list[TransferRecord]:
    out: list[TransferRecord] = []
    for item in payload.get("response", []):
        pid = str(item["player"]["id"])
        for t in item.get("transfers", []):
            teams = t.get("teams") or {}
            src, dst = teams.get("out") or {}, teams.get("in") or {}
            fee_eur, fee_type = parse_fee(t.get("type"))
            out.append(
                TransferRecord(
                    source=SOURCE,
                    source_player_id=pid,
                    transfer_date=_date(t.get("date")),
                    from_club=ClubRef(str(src["id"]), src["name"]) if src.get("id") else None,
                    to_club=ClubRef(str(dst["id"]), dst["name"]) if dst.get("id") else None,
                    fee_eur=fee_eur,
                    fee_type=fee_type,
                    fee_raw=t.get("type"),
                )
            )
    return out


def parse_league_season(payload: dict[str, Any], season: int) -> dict[str, Any] | None:
    """Return {competition, start, end, current} for one league-season."""
    for item in payload.get("response", []):
        league, country = item["league"], item.get("country") or {}
        for s in item.get("seasons", []):
            if s.get("year") == season:
                return {
                    "competition": CompetitionRef(
                        str(league["id"]),
                        league["name"],
                        country.get("name"),
                        (league.get("type") or "").lower() or None,
                    ),
                    "start": _date(s.get("start")),
                    "end": _date(s.get("end")),
                    "current": bool(s.get("current")),
                }
    return None


class RateLimited(ProviderError):
    """Per-minute limit hit (body error `rateLimit`). Retryable after a pause."""


def _check_errors(payload: dict[str, Any]) -> None:
    errors = payload.get("errors")
    if not errors:
        return
    keys = set(errors) if isinstance(errors, dict) else set()
    text = str(errors)
    if "rateLimit" in keys:
        raise RateLimited(f"API-Football: {text}")
    if "requests" in keys or "request limit" in text.lower():
        raise QuotaExhausted(f"API-Football: {text}")
    raise ProviderError(f"API-Football: {text}")


# ---------------------------------------------------------------- provider


class ApiFootballProvider:
    name = SOURCE
    license = "licensed"
    attribution = "Data provided by API-Football (api-sports.io)"

    def __init__(
        self,
        api_key: str,
        *,
        cache_dir: Path | None = None,
        quota: QuotaTracker | None = None,
        client: HttpClient | None = None,
    ) -> None:
        self.client = client or HttpClient(
            source=SOURCE,
            base_url=BASE_URL,
            headers={"x-apisports-key": api_key},
            min_interval_s=6.5,  # 10 requests/minute on the free plan
            cache_dir=cache_dir,
            quota=quota,
        )

    @property
    def requests_made(self) -> int:
        return self.client.requests_made

    def _get(self, endpoint: str, params: dict[str, Any], *, use_cache: bool = True) -> Any:
        for attempt in range(3):
            payload = self.client.get_json(
                endpoint, params, use_cache=use_cache, is_ok=lambda d: not d.get("errors")
            )
            try:
                _check_errors(payload)
                return payload
            except RateLimited:
                if attempt == 2:
                    raise
                self.client.sleep(61.0)  # the per-minute window resets
        raise AssertionError("unreachable")

    # --- page-level calls used by the ETL

    def fetch_players_page(
        self, league_id: int, season: int, page: int, *, use_cache: bool = True
    ) -> FetchResult:
        payload = self._get(
            "/players", {"league": league_id, "season": season, "page": page}, use_cache=use_cache
        )
        return parse_players_page(payload, season, league_id)

    def fetch_league_season(self, league_id: int, season: int) -> dict[str, Any] | None:
        return parse_league_season(
            self._get("/leagues", {"id": league_id, "season": season}), season
        )

    def fetch_team_transfers(self, team_id: int) -> list[TransferRecord]:
        return parse_transfers(self._get("/transfers", {"team": team_id}))

    # --- Provider protocol

    def iter_players(self, league_id: int, season: int) -> Iterator[FetchResult]:
        page, total = 1, 1
        while page <= total:
            result = self.fetch_players_page(league_id, season, page)
            total = result.total_pages or 1
            yield result
            page += 1

    def search_players(self, filters: SearchFilters) -> FetchResult:
        """Fetch every player of the given competitions/season. Expensive (~50 requests per
        league-season); only the ETL should call this - never an API request."""
        if filters.season is None or not filters.competition_ids:
            raise ValueError("api_football search needs season and competition_ids")
        players: list[PlayerRecord] = []
        stats: list[SeasonStatsRecord] = []
        for comp in filters.competition_ids:
            for result in self.iter_players(int(comp), filters.season):
                players.extend(result.players)
                stats.extend(result.stats)
        return FetchResult(players=players, stats=stats, requests_made=self.requests_made)

    def get_player(self, player_id: str) -> PlayerRecord | None:
        payload = self._get("/players/profiles", {"player": player_id})
        items = payload.get("response", [])
        return parse_player(items[0]) if items else None

    def get_season_stats(self, player_id: str, season: int) -> list[SeasonStatsRecord]:
        payload = self._get("/players", {"id": player_id, "season": season})
        return [row for item in payload.get("response", []) for row in parse_stats(item, season)]

    def get_market_values(self, player_id: str) -> list[MarketValueRecord]:
        return []  # API-Football has no market values (see docs/decisions.md, ADR-006)
