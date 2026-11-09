from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from wescout.config import load_settings
from wescout.models import SearchFilters
from wescout.providers.api_football import (
    BASE_URL,
    ApiFootballProvider,
    parse_fee,
    parse_league_season,
    parse_players_page,
    parse_transfers,
)
from wescout.providers.base import Provider, ProviderBlocked, ProviderError, QuotaExhausted
from wescout.providers.http import HttpClient, QuotaTracker
from wescout.providers.registry import LocalScrapersDisabled, create_provider


def _client(handler: Any, tmp_path: Path | None = None, **kw: Any) -> HttpClient:
    return HttpClient(
        source="api_football",
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
        cache_dir=tmp_path,
        **kw,
    )


# ---------------------------------------------------------------- parsing


def test_players_page_parsing(load_fixture: Any) -> None:
    result = parse_players_page(
        load_fixture("api_football/players_league39_season2023_page1.json"), 2023, 39
    )
    assert result.total_pages == 51
    akanji = next(p for p in result.players if p.source_player_id == "5")
    assert akanji.date_of_birth == date(1995, 7, 19)
    assert akanji.height_cm == 188
    assert akanji.position == "DF"

    row = next(s for s in result.stats if s.source_player_id == "5")
    assert (row.appearances, row.starts, row.minutes) == (34, 32, 2514)
    assert row.rating == pytest.approx(7.27931)
    assert (row.goals, row.assists, row.key_passes) == (2, 0, 13)
    assert (row.tackles, row.interceptions, row.total_passes) == (42, 23, 2296)
    assert row.accurate_passes is None  # ambiguous field kept in extra
    assert row.extra["passes_accuracy_raw"] == 74
    assert row.club.name == "Manchester City"
    assert row.competition.source_id == "39"


def test_null_rating_and_goalkeeper(load_fixture: Any) -> None:
    result = parse_players_page(
        load_fixture("api_football/players_league39_season2023_page1.json"), 2023, 39
    )
    by_name = {p.name: p for p in result.players}
    assert by_name["E. Horvath"].position == "GK"
    costa_stats = [
        s for s in result.stats if s.source_player_id == by_name["Diego Costa"].source_player_id
    ]
    assert all(s.rating is None for s in costa_stats)


def test_entries_without_playing_time_are_skipped(load_fixture: Any) -> None:
    payload = load_fixture("api_football/players_league39_season2023_page1.json")
    nakamba = next(i for i in payload["response"] if i["player"]["name"] == "M. Nakamba")
    played = [
        s for s in nakamba["statistics"] if s["games"]["appearences"] or s["games"]["minutes"]
    ]
    result = parse_players_page({"response": [nakamba]}, 2023, 39)
    assert len(result.stats) == len(played)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("€ 17.5M", (17_500_000, "fee")),
        ("1.7M €", (1_700_000, "fee")),
        ("€ 100K", (100_000, "fee")),
        ("&pound; 1.5M", (None, "fee")),  # non-euro: no FX conversion
        ("Loan", (None, "loan")),
        ("Back from Loan", (None, "loan_end")),
        ("Return from loan", (None, "loan_end")),
        ("Free Transfer", (0, "free")),
        ("Free agent", (0, "free")),
        ("N/A", (None, "unknown")),
        ("-", (None, "unknown")),
        (None, (None, "unknown")),
    ],
)
def test_parse_fee(raw: str | None, expected: tuple[int | None, str]) -> None:
    assert parse_fee(raw) == expected


def test_transfers_parsing(load_fixture: Any) -> None:
    transfers = parse_transfers(load_fixture("api_football/transfers_team50.json"))
    assert transfers
    assert all(t.fee_raw is not None for t in transfers)
    assert {t.fee_type for t in transfers} >= {"loan", "free", "unknown", "fee"}


def test_league_season_parsing(load_fixture: Any) -> None:
    info = parse_league_season(load_fixture("api_football/leagues_39_season2023.json"), 2023)
    assert info is not None
    assert info["start"] == date(2023, 8, 11)
    assert info["end"] == date(2024, 5, 19)
    assert info["competition"].country == "England"


# ---------------------------------------------------------------- provider + HTTP client


def test_provider_satisfies_protocol() -> None:
    assert isinstance(ApiFootballProvider("k"), Provider)


def test_free_plan_season_error_is_not_cached(load_fixture: Any, tmp_path: Path) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json=load_fixture("api_football/players_season2025_free_plan_error.json")
        )

    provider = ApiFootballProvider("k", client=_client(handler, tmp_path))
    for _ in range(2):
        with pytest.raises(ProviderError, match="Free plans"):
            provider.fetch_players_page(39, 2025, 1)
    assert len(calls) == 2  # error responses are never served from cache


def test_successful_response_is_cached(load_fixture: Any, tmp_path: Path) -> None:
    calls = []
    payload = load_fixture("api_football/players_league39_season2023_page1.json")

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["x-apisports-key"] == "k"
        assert "WeScout" in request.headers["user-agent"]
        return httpx.Response(200, json=payload)

    client = _client(handler, tmp_path, headers={"x-apisports-key": "k"})
    provider = ApiFootballProvider("k", client=client)
    first = provider.fetch_players_page(39, 2023, 1)
    second = provider.fetch_players_page(39, 2023, 1)
    assert len(calls) == 1
    assert first == second
    assert provider.requests_made == 1


def test_quota_stops_before_reserve() -> None:
    quota = QuotaTracker(daily_limit=100, reserve=5, used_today=94)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [], "response": [], "paging": {"total": 1}})

    client = _client(handler, quota=quota)
    client.get_json("/status")  # 6 left -> allowed
    with pytest.raises(QuotaExhausted):
        client.get_json("/status", {"x": 1})  # 5 left == reserve -> stop


def test_quota_uses_provider_header_when_lower() -> None:
    quota = QuotaTracker(daily_limit=100, reserve=5)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"errors": []}, headers={"x-ratelimit-requests-remaining": "5"}
        )

    client = _client(handler, quota=quota)
    client.get_json("/status")
    with pytest.raises(QuotaExhausted):
        client.get_json("/status", {"again": 1})


def test_daily_limit_body_error_raises_quota() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"errors": {"requests": "You have reached the request limit for the day"}}
        )

    with pytest.raises(QuotaExhausted):
        ApiFootballProvider("k", client=_client(handler)).fetch_players_page(39, 2023, 1)


def test_rate_limit_body_error_retries(load_fixture: Any) -> None:
    payload = load_fixture("api_football/players_league39_season2023_page1.json")
    responses = [{"errors": {"rateLimit": "Too many requests"}}, payload]
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    client = _client(handler)
    client.sleep = slept.append
    result = ApiFootballProvider("k", client=client).fetch_players_page(39, 2023, 1)
    assert result.players
    assert 61.0 in slept


def test_server_errors_back_off_then_succeed() -> None:
    statuses = [503, 429, 200]
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(statuses.pop(0), json={"errors": []})

    client = _client(handler, min_interval_s=1.0)
    client.sleep = slept.append
    assert client.get_json("/status") == {"errors": []}
    assert client.requests_made == 3
    assert [s for s in slept if s >= 2.0] == [2.0, 4.0]


def test_blocked_is_never_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403)

    with pytest.raises(ProviderBlocked):
        _client(handler).get_json("/x")
    assert len(calls) == 1


def test_min_interval_between_requests() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    client = _client(lambda r: httpx.Response(200, json={}), min_interval_s=6.5)
    client.clock = lambda: now[0]
    client.sleep = sleep
    client.get_json("/a")
    now[0] += 1.0
    client.get_json("/b")
    assert slept == [pytest.approx(5.5)]


def test_search_requires_scope() -> None:
    with pytest.raises(ValueError):
        ApiFootballProvider("k").search_players(SearchFilters())


# ---------------------------------------------------------------- registry


def test_scrapers_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_LOCAL_SCRAPERS", raising=False)
    settings = load_settings(env_file=None)
    with pytest.raises(LocalScrapersDisabled):
        create_provider("transfermarkt", settings)


def test_registry_needs_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    with pytest.raises(ProviderError, match="API_FOOTBALL_KEY"):
        create_provider("api_football", load_settings(env_file=None))


def test_fixtures_contain_no_secrets() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    for path in fixtures.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "x-apisports-key" not in text
        json.loads(text)


def test_team_squad_page_keeps_league_rows_only(load_fixture: Any) -> None:
    payload = load_fixture("api_football/players_team50_season2023_page1.json")
    result = parse_players_page(payload, 2023, 39)
    assert result.total_pages == 3
    assert {s.competition.source_id for s in result.stats} == {"39"}
    # Without a league filter, cups/Europe are kept but entries without a league id are not.
    everything = parse_players_page(payload, 2023)
    assert len(everything.stats) > len(result.stats)
    assert all(s.competition.source_id != "None" for s in everything.stats)


def test_teams_parsing(load_fixture: Any) -> None:
    from wescout.providers.api_football import parse_teams

    teams = parse_teams(load_fixture("api_football/teams_league39_season2023.json"))
    assert {t.name for t in teams} == {"Manchester United", "Liverpool", "Manchester City"}
