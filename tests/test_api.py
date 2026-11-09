from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wescout.api.main import create_app
from wescout.config import load_settings
from wescout.db import repository as repo
from wescout.models import ClubRef, CompetitionRef, MarketValueRecord, PlayerRecord
from wescout.models import SeasonStatsRecord as S
from wescout.resolve import resolve_players

T0 = datetime(2026, 11, 9)
PL = CompetitionRef("39", "Premier League", "England")
TODAY = date.today()


def _dob(age: int) -> date:
    return date(TODAY.year - age, 1, 1)


@pytest.fixture
def seeded(db: Any) -> Any:
    """Licensed: 3 players. Scraped (local_scrape): a market value, a detailed position,
    and one scraped-only player. None of the scraped data may appear in PUBLIC_MODE."""
    af, tm = "api_football", "transfermarkt"
    repo.register_source(db, tm, "local_scrape", None, None)
    players = [
        PlayerRecord(af, "1", "Young Fullback", date_of_birth=_dob(21), position="DF"),
        PlayerRecord(af, "2", "Old Centreback", date_of_birth=_dob(31), position="DF"),
        PlayerRecord(af, "3", "Young Winger", date_of_birth=_dob(20), position="FW"),
        PlayerRecord(tm, "t1", "Young Fullback", date_of_birth=_dob(21), detailed_position="lb"),
        PlayerRecord(tm, "t9", "Scraped Only", date_of_birth=_dob(22), detailed_position="lb"),
    ]
    repo.upsert_source_players(db, players, T0)
    city, spurs = ClubRef("50", "Manchester City"), ClubRef("47", "Tottenham")
    repo.upsert_season_stats(
        db,
        [
            # Player 1 moved mid-season: two clubs, stats must be summed.
            S(af, "1", PL, city, 2023, "DF", 10, 8, 900, 7.0, 1, 2, 5, 18, 9, 4, None, None, 600),
            S(af, "1", PL, spurs, 2023, "DF", 10, 10, 900, 8.0, 0, 1, 5, 18, 9, 4),
            S(af, "2", PL, city, 2023, "DF", 30, 30, 2700, 6.8, 2, 0, 3, 40, 30, 10),
            S(af, "3", PL, spurs, 2023, "FW", 25, 20, 1800, 7.5, 9, 6, 40, 5, 2, 8),
            S(af, "3", PL, spurs, 2022, "FW", 20, 15, 1200, 6.9, 3, 2),
        ],
        T0,
        season_complete=True,
    )
    repo.upsert_season_stats(db, [S(tm, "t9", PL, city, 2023, "DF", 5, 5, 450, 7.9)], T0)
    repo.upsert_market_values(
        db, [MarketValueRecord(tm, "t1", date(2026, 11, 1), 12_000_000, city)], T0
    )
    resolve_players(db)
    return db


def _client(db: Any, public: bool) -> TestClient:
    settings = replace(load_settings(env_file=None), public_mode=public)
    return TestClient(create_app(settings, con=db))


def test_health_and_positions(seeded: Any) -> None:
    with _client(seeded, True) as c:
        assert c.get("/api/health").json()["success"] is True
        positions = c.get("/api/positions").json()["positions"]
        assert {"id": 4, "code": "lb", "name": "Left Back"} in positions


def test_search_shape_matches_frontend(seeded: Any) -> None:
    with _client(seeded, True) as c:
        body = c.get("/api/players/search").json()
    assert body["success"] is True and body["season"] == 2023
    assert body["count"] == len(body["players"]) == 3
    expected = {
        "player_id", "player_name", "club_name", "position", "price", "price_int", "rating",
        "goals", "assists", "key_passes", "minutes_played", "tackles_per_90",
        "interceptions_per_90", "dribbled_past_per_90", "big_chances_created",
        "pass_completion", "age",
    }  # fmt: skip
    assert expected <= set(body["players"][0])
    assert body["attribution"] == ["Data provided by API-Football (api-sports.io)"]


def test_mid_season_transfer_is_aggregated(seeded: Any) -> None:
    with _client(seeded, True) as c:
        players = c.get("/api/players/search").json()["players"]
    p = next(p for p in players if p["player_name"] == "Young Fullback")
    assert p["minutes_played"] == 1800 and p["goals"] == 1 and p["assists"] == 3
    assert p["rating"] == pytest.approx(7.5)  # minutes-weighted (7.0 and 8.0, equal minutes)
    assert p["tackles_per_90"] == pytest.approx(36 * 90 / 1800)
    assert p["club_name"] in {"Manchester City", "Tottenham"}


def test_filters(seeded: Any) -> None:
    with _client(seeded, True) as c:
        young = c.get("/api/players/search", params={"max_age": 23}).json()["players"]
        assert {p["player_name"] for p in young} == {"Young Fullback", "Young Winger"}
        lb = c.get("/api/players/search", params={"position": "lb", "max_age": 23}).json()
        # Public: no detailed positions known -> coarse DF fallback.
        assert [p["player_name"] for p in lb["players"]] == ["Young Fullback"]
        assert lb["players"][0]["position"] == "DF"
        season = c.get("/api/players/search", params={"season": 2022}).json()
        assert [p["player_name"] for p in season["players"]] == ["Young Winger"]
        mins = c.get("/api/players/search", params={"min_minutes": 2000}).json()
        assert [p["player_name"] for p in mins["players"]] == ["Old Centreback"]


def test_public_mode_hides_all_scraped_data(seeded: Any) -> None:
    with _client(seeded, True) as c:
        body = c.get("/api/players/search").json()
    names = {p["player_name"] for p in body["players"]}
    assert "Scraped Only" not in names
    for p in body["players"]:
        assert p["price_int"] is None and p["price"] is None  # value came from a scraper
        assert p["position"] != "LB"  # detailed position came from a scraper


def test_private_mode_uses_scraped_data(seeded: Any) -> None:
    with _client(seeded, False) as c:
        body = c.get("/api/players/search", params={"position": "lb"}).json()
    by_name = {p["player_name"]: p for p in body["players"]}
    assert by_name["Young Fullback"]["price_int"] == 12_000_000
    assert by_name["Young Fullback"]["price"] == "€12.00m"
    assert by_name["Young Fullback"]["position"] == "LB"
    assert "Scraped Only" in by_name
    assert by_name["Young Fullback"]["minutes_played"] == 1800  # licensed stats preferred


def test_value_filter_in_private_mode(seeded: Any) -> None:
    with _client(seeded, False) as c:
        body = c.get("/api/players/search", params={"max_value": 10_000_000}).json()
    names = {p["player_name"] for p in body["players"]}
    assert "Young Fullback" not in names  # known value 12M > 10M
    assert "Old Centreback" in names  # unknown value is not filtered out


@pytest.mark.parametrize(
    "params",
    [{"min_age": 30, "max_age": 20}, {"min_value": 5, "max_value": 1}, {"position": "xx"}],
)
def test_bad_input_returns_400(seeded: Any, params: dict[str, Any]) -> None:
    with _client(seeded, True) as c:
        r = c.get("/api/players/search", params=params)
    assert r.status_code == 400 and r.json()["success"] is False


def test_empty_database(db: Any) -> None:
    with _client(db, True) as c:
        body = c.get("/api/players/search").json()
    assert body == {
        "success": True, "count": 0, "players": [], "season": None, "public_mode": True,
        "attribution": [],
    }  # fmt: skip


# ---------------------------------------------------------------- frontend endpoints


def test_multi_position_and_sort(seeded: Any) -> None:
    with _client(seeded, True) as c:
        both = c.get("/api/players/search", params={"positions": "lb,st"}).json()["players"]
        assert {p["player_name"] for p in both} == {
            "Young Fullback", "Old Centreback", "Young Winger"
        }  # fmt: skip
        by_minutes = c.get("/api/players/search", params={"sort": "minutes"}).json()["players"]
        assert by_minutes[0]["player_name"] == "Old Centreback"
        youngest = c.get("/api/players/search", params={"sort": "age"}).json()["players"]
        assert youngest[0]["player_name"] == "Young Winger"
        assert c.get("/api/players/search", params={"sort": "drop table"}).status_code == 400


def test_competition_filter(seeded: Any) -> None:
    with _client(seeded, True) as c:
        meta = c.get("/api/meta").json()
        pl = meta["competitions"][0]["id"]
        hit = c.get("/api/players/search", params={"competition": pl}).json()
        miss = c.get("/api/players/search", params={"competition": pl + 999}).json()
    assert hit["count"] == 3 and hit["players"][0]["competition"] == "Premier League"
    assert miss["count"] == 0


def test_meta_lists_only_public_data(seeded: Any) -> None:
    with _client(seeded, True) as c:
        public = c.get("/api/meta").json()
    with _client(seeded, False) as c:
        local = c.get("/api/meta").json()
    assert public["seasons"] == [
        {"start_year": 2023, "label": "2023/24"}, {"start_year": 2022, "label": "2022/23"}
    ]  # fmt: skip

    def total(meta: dict[str, Any]) -> int:
        return sum(s["players"] for c in meta["competitions"] for s in c["seasons"])

    # The scraped-only player counts in local mode but not in public mode. (Competitions are
    # mapped per source, so its scraped "Premier League" is a separate local-only entry.)
    assert total(local) == total(public) + 1
    assert len(public["competitions"]) == 1
    assert public["public_mode"] is True and local["public_mode"] is False


def test_player_detail(seeded: Any) -> None:
    with _client(seeded, True) as c:
        search = c.get("/api/players/search").json()["players"]
        pid = next(p["player_id"] for p in search if p["player_name"] == "Young Winger")
        body = c.get(f"/api/players/{pid}").json()
    player = body["player"]
    assert player["name"] == "Young Winger" and player["age"] == 20
    assert [s["season"] for s in player["seasons"]] == ["2023/24", "2022/23"]
    assert player["seasons"][0]["per90"]["goals"] == pytest.approx(9 * 90 / 1800)
    assert player["sofascore_ratings"] == []


def test_player_detail_hides_scraped_only_player_in_public_mode(seeded: Any) -> None:
    with _client(seeded, False) as c:
        local = c.get("/api/players/search").json()["players"]
        pid = next(p["player_id"] for p in local if p["player_name"] == "Scraped Only")
        assert c.get(f"/api/players/{pid}").status_code == 200
    with _client(seeded, True) as c:
        r = c.get(f"/api/players/{pid}")
        assert r.status_code == 404 and r.json()["success"] is False
        assert c.get("/api/players/999999").status_code == 404


def test_public_player_detail_has_no_scraped_fields(seeded: Any) -> None:
    with _client(seeded, True) as c:
        search = c.get("/api/players/search").json()["players"]
        pid = next(p["player_id"] for p in search if p["player_name"] == "Young Fullback")
        player = c.get(f"/api/players/{pid}").json()["player"]
    assert player["position"] == "DF"  # 'LB' exists only in scraped data
