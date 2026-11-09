from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import httpx
import pytest

from wescout.db import repository as repo
from wescout.etl import RunSummary, _BudgetReached, run_api_football
from wescout.providers.api_football import BASE_URL, ApiFootballProvider
from wescout.providers.http import HttpClient


@pytest.fixture
def api(load_fixture: Any, tmp_path: Path) -> tuple[ApiFootballProvider, list[str]]:
    """Mock API for league 39 / 2023: 3 clubs; club 50 has 2 squad pages, the others 1."""
    base = load_fixture("api_football/players_team50_season2023_page1.json")
    leagues = load_fixture("api_football/leagues_39_season2023.json")
    teams = load_fixture("api_football/teams_league39_season2023.json")
    transfers = load_fixture("api_football/transfers_team50.json")
    calls: list[str] = []

    def squad_page(team: int, page: int) -> dict[str, Any]:
        payload = copy.deepcopy(base)
        payload["paging"] = {"current": page, "total": 2 if team == 50 else 1}
        for item in payload["response"]:
            item["player"]["id"] += team * 1000 + page * 100
            for stat in item["statistics"]:
                stat["team"]["id"] = team
        return payload

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        path, params = request.url.path, dict(request.url.params)
        if path == "/leagues":
            return httpx.Response(200, json=leagues)
        if path == "/teams":
            return httpx.Response(200, json=teams)
        if path == "/players":
            return httpx.Response(200, json=squad_page(int(params["team"]), int(params["page"])))
        if path == "/transfers":
            return httpx.Response(200, json=transfers)
        return httpx.Response(404)

    client = HttpClient(
        source="api_football", base_url=BASE_URL, transport=httpx.MockTransport(handler),
        sleep=lambda _s: None, cache_dir=tmp_path,
    )  # fmt: skip
    return ApiFootballProvider("k", client=client), calls


def _count(db: Any, table: str) -> int:
    return int(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_full_load(db: Any, api: tuple[ApiFootballProvider, list[str]]) -> None:
    provider, _calls = api
    summary = RunSummary(1, "api_football")
    run_api_football(db, provider, [39], [2023], summary, transfers=True)

    assert summary.pages_done == 4  # 1 + 1 + 2 squad pages
    assert _count(db, "source_players") == 12
    assert _count(db, "clubs") >= 3
    assert _count(db, "player_season_stats") > 0
    assert _count(db, "transfers") > 0
    season = db.execute("SELECT start_date, end_date, is_complete FROM seasons").fetchone()
    assert str(season[0]) == "2023-08-11" and season[2] is True
    # Season row from /leagues and from stats are the same row (one competition, one season).
    assert _count(db, "competitions") == 1 and _count(db, "seasons") == 1
    assert db.execute("SELECT bool_and(s.is_complete) FROM seasons s").fetchone()[0] is True


def test_resume_after_budget_stop(db: Any, api: tuple[ApiFootballProvider, list[str]]) -> None:
    provider, calls = api
    summary = RunSummary(1, "api_football")
    with pytest.raises(_BudgetReached):
        # league + teams + first club's page
        run_api_football(db, provider, [39], [2023], summary, max_requests=3)
    assert summary.pages_done == 1
    assert len(calls) == 3

    summary2 = RunSummary(2, "api_football")
    run_api_football(db, provider, [39], [2023], summary2)
    assert summary2.pages_done == 3  # the 3 pages not loaded yet
    assert len(calls) == 6  # teams + first page came from the disk cache
    assert _count(db, "source_players") == 12


def test_rerun_is_idempotent(db: Any, api: tuple[ApiFootballProvider, list[str]]) -> None:
    provider, calls = api
    run_api_football(db, provider, [39], [2023], RunSummary(1, "api_football"))
    before = {t: _count(db, t) for t in ("source_players", "player_season_stats", "clubs")}
    n_calls = len(calls)
    summary = RunSummary(2, "api_football")
    run_api_football(db, provider, [39], [2023], summary)
    assert summary.pages_done == 0 and summary.pages_skipped == 4
    assert len(calls) == n_calls  # nothing fetched again
    assert {t: _count(db, t) for t in before} == before


def test_api_usage_is_persisted(db: Any, api: tuple[ApiFootballProvider, list[str]]) -> None:
    from wescout.providers.http import QuotaTracker

    provider, _ = api
    day = repo.utcnow().date()
    provider.client.quota = QuotaTracker(
        daily_limit=100, on_request=lambda: repo.add_api_usage(db, "api_football", day)
    )
    run_api_football(db, provider, [39], [2023], RunSummary(1, "api_football"))
    assert repo.api_usage_on(db, "api_football", day) == 6  # league + teams + 4 pages
