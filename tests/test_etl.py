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
    """Mock API: league 39 / 2023 with 2 pages (page 2 = same players, different IDs)."""
    page1 = load_fixture("api_football/players_league39_season2023_page1.json")
    page1["paging"]["total"] = 2
    page2 = copy.deepcopy(page1)
    page2["paging"]["current"] = 2
    for item in page2["response"]:
        item["player"]["id"] += 100_000
    leagues = load_fixture("api_football/leagues_39_season2023.json")
    transfers = load_fixture("api_football/transfers_team50.json")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        path, params = request.url.path, dict(request.url.params)
        if path == "/leagues":
            return httpx.Response(200, json=leagues)
        if path == "/players":
            return httpx.Response(200, json=page1 if params["page"] == "1" else page2)
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

    assert summary.pages_done == 2
    assert _count(db, "source_players") == 8
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
        run_api_football(db, provider, [39], [2023], summary, max_requests=2)  # league + page 1
    assert summary.pages_done == 1
    assert len(calls) == 2

    summary2 = RunSummary(2, "api_football")
    run_api_football(db, provider, [39], [2023], summary2)
    assert summary2.pages_done == 1  # only page 2 is new
    assert len(calls) == 3  # page 1 came from the disk cache, league from the checkpoint
    assert _count(db, "source_players") == 8


def test_rerun_is_idempotent(db: Any, api: tuple[ApiFootballProvider, list[str]]) -> None:
    provider, calls = api
    run_api_football(db, provider, [39], [2023], RunSummary(1, "api_football"))
    before = {t: _count(db, t) for t in ("source_players", "player_season_stats", "clubs")}
    n_calls = len(calls)
    summary = RunSummary(2, "api_football")
    run_api_football(db, provider, [39], [2023], summary)
    assert summary.pages_done == 0 and summary.pages_skipped == 2
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
    assert repo.api_usage_on(db, "api_football", day) == 3  # league + 2 pages
