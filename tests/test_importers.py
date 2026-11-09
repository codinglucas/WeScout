from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wescout.api.main import create_app
from wescout.api.search import last_completed_seasons
from wescout.config import load_settings
from wescout.db import repository as repo
from wescout.importers import CsvFormatError, import_ratings_csv, parse_season
from wescout.models import ClubRef, CompetitionRef, PlayerRecord, SeasonStatsRecord
from wescout.resolve import resolve_players

FIXTURE = Path(__file__).parent / "fixtures" / "ratings" / "sofascore_ratings.csv"
T0 = datetime(2026, 11, 9)
PL = CompetitionRef("39", "Premier League")


def _anchor(
    db: Any, spid: str, name: str, dob: date, club: str, first: str = "", last: str = ""
) -> None:
    repo.upsert_source_players(
        db,
        [PlayerRecord("api_football", spid, name, first or None, last or None, dob, position="DF")],
        T0,
    )
    repo.upsert_season_stats(
        db,
        [SeasonStatsRecord("api_football", spid, PL, ClubRef(club, club), 2023, "DF", 30, 30,
                           2500, 7.0)],
        T0,
    )  # fmt: skip


@pytest.fixture
def anchored(db: Any) -> Any:
    _anchor(db, "5", "M. Akanji", date(1995, 7, 19), "Manchester City", "Manuel Obafemi", "Akanji")
    _anchor(db, "6", "Danilo", date(1991, 7, 15), "Juventus")
    _anchor(db, "7", "Danilo", date(2001, 4, 29), "Nottingham Forest")
    # Two Gabriels at Arsenal: a name-only match must not pick one.
    _anchor(db, "8", "Gabriel", date(1997, 12, 19), "Arsenal", "Gabriel", "dos Santos Magalhães")
    _anchor(db, "9", "Gabriel Jesus", date(1997, 4, 3), "Arsenal", "Gabriel Fernando", "de Jesus")
    resolve_players(db)
    return db


def _pid(db: Any, source: str, spid: str) -> Any:
    row = db.execute(
        "SELECT player_id FROM source_players WHERE source = ? AND source_player_id = ?",
        [source, spid],
    ).fetchone()
    return row[0] if row else None


@pytest.mark.parametrize(
    ("text", "year"), [("2023/24", 2023), ("23/24", 2023), ("2023", 2023), ("2023-24", 2023)]
)
def test_parse_season(text: str, year: int) -> None:
    assert parse_season(text) == year


def test_last_completed_seasons() -> None:
    assert last_completed_seasons(date(2026, 11, 9)) == [2025, 2024, 2023]
    assert last_completed_seasons(date(2026, 3, 1)) == [2024, 2023, 2022]


def test_import_matches_and_reviews(anchored: Any) -> None:
    stats = import_ratings_csv(anchored, FIXTURE)
    assert stats.skipped_rows and "line 9" in stats.skipped_rows[0]  # 'eleven'
    assert stats.players == 4  # Akanji, Danilo(dob), Gabriel, Unknown Kid
    # Akanji: name + club, no DOB -> matched; Danilo: DOB decides between namesakes.
    assert _pid(anchored, "sofascore_manual", "manuel-akanji") == _pid(
        anchored, "api_football", "5"
    )
    assert _pid(anchored, "sofascore_manual", "danilo:1991-07-15") == _pid(
        anchored, "api_football", "6"
    )
    # Ambiguous (two Gabriels at Arsenal) and unknown club -> review, not guessed.
    assert _pid(anchored, "sofascore_manual", "gabriel") is None
    assert _pid(anchored, "sofascore_manual", "unknown-kid") is None
    assert (stats.matched, stats.review) == (2, 2)
    reviews = {
        r[0] for r in anchored.execute("SELECT source_player_id FROM match_reviews").fetchall()
    }
    assert reviews == {"gabriel", "unknown-kid"}
    # Duplicate season row (2024/25 twice) stored once.
    n = anchored.execute(
        "SELECT count(*) FROM player_season_ratings WHERE source_player_id = 'manuel-akanji'"
    ).fetchone()[0]
    assert n == 3  # 2023, 2024, 2020


def test_reimport_is_idempotent_and_reflects_edits(anchored: Any, tmp_path: Path) -> None:
    import_ratings_csv(anchored, FIXTURE)
    import_ratings_csv(anchored, FIXTURE)
    assert (
        anchored.execute("SELECT count(*) FROM player_season_ratings").fetchone()[0] == 6
    )  # 3 Akanji + Danilo + Gabriel + Unknown Kid
    edited = tmp_path / "r.csv"
    edited.write_text(
        "player_name,club,season,rating,minutes\nManuel Akanji,Manchester City,2023/24,6.5,2000\n",
        encoding="utf-8",
    )
    import_ratings_csv(anchored, edited)
    rows = anchored.execute(
        "SELECT season_start_year, rating FROM player_season_ratings"
        " WHERE source_player_id = 'manuel-akanji'"
    ).fetchall()
    assert rows == [(2023, 6.5)]


def test_resolver_leaves_reviews_alone(anchored: Any) -> None:
    import_ratings_csv(anchored, FIXTURE)
    before = anchored.execute("SELECT count(*) FROM players").fetchone()[0]
    stats = resolve_players(anchored)
    assert stats.new == 0
    assert anchored.execute("SELECT count(*) FROM players").fetchone()[0] == before


def test_missing_columns_rejected(tmp_path: Path, db: Any) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("name,club\nX,Y\n", encoding="utf-8")
    with pytest.raises(CsvFormatError, match="player_name"):
        import_ratings_csv(db, bad)


def _search(db: Any, public: bool) -> dict[str, Any]:
    settings = replace(load_settings(env_file=None), public_mode=public)
    with TestClient(create_app(settings, con=db)) as c:
        return c.get("/api/players/search").json()


def test_api_shows_ratings_only_in_local_mode(
    anchored: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import wescout.api.search as search

    monkeypatch.setattr(
        search, "date", type("D", (), {"today": staticmethod(lambda: date(2026, 11, 9))})
    )
    import_ratings_csv(anchored, FIXTURE)

    local = {p["player_name"]: p for p in _search(anchored, public=False)["players"]}
    akanji = local["M. Akanji"]["sofascore_ratings"]
    # Last 3 completed seasons only (2020/21 excluded), newest first.
    assert [r["season"] for r in akanji] == ["2024/25", "2023/24"]
    assert akanji[1] == {"season": "2023/24", "rating": 7.1, "minutes": 2000,
                         "clubs": ["Manchester City"]}  # fmt: skip
    by_id = {p["player_id"]: p for p in _search(anchored, public=False)["players"]}
    danilo_1991 = by_id[_pid(anchored, "api_football", "6")]
    assert danilo_1991["sofascore_ratings"][0]["rating"] == 7.0
    assert by_id[_pid(anchored, "api_football", "7")]["sofascore_ratings"] == []

    public = _search(anchored, public=True)["players"]
    assert public and all(p["sofascore_ratings"] == [] for p in public)
    assert "sofascore_manual" not in str(_search(anchored, public=True)["attribution"])
