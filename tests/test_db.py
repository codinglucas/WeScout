from __future__ import annotations

from datetime import date, datetime
from typing import Any

from wescout.db import repository as repo
from wescout.db.connection import migrate
from wescout.models import (
    ClubRef,
    CompetitionRef,
    MarketValueRecord,
    PlayerRecord,
    SeasonStatsRecord,
    TransferRecord,
)

T0 = datetime(2026, 11, 1, 12, 0)
T1 = datetime(2026, 11, 2, 12, 0)
PL = CompetitionRef("39", "Premier League", "England", "league")
CITY = ClubRef("50", "Manchester City", "England")


def _stats(**overrides: Any) -> SeasonStatsRecord:
    base: dict[str, Any] = dict(
        source="api_football", source_player_id="5", competition=PL, club=CITY,
        season_start_year=2023, position="DF", appearances=34, minutes=2514, goals=2,
    )  # fmt: skip
    base.update(overrides)
    return SeasonStatsRecord(**base)


def _count(db: Any, table: str) -> int:
    return int(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_migrations_are_idempotent(db: Any) -> None:
    assert migrate(db) == []  # already applied by the fixture
    licenses = dict(db.execute("SELECT source, license FROM sources").fetchall())
    assert licenses["api_football"] == "licensed"


def test_stats_upsert_is_idempotent_and_updates(db: Any) -> None:
    repo.upsert_season_stats(db, [_stats()], T0)
    repo.upsert_season_stats(db, [_stats()], T0)
    assert _count(db, "player_season_stats") == 1
    assert _count(db, "clubs") == 1
    assert _count(db, "competitions") == 1
    assert _count(db, "seasons") == 1

    repo.upsert_season_stats(db, [_stats(goals=3)], T1, season_complete=True)
    goals, fetched = db.execute("SELECT goals, fetched_at FROM player_season_stats").fetchone()
    assert (goals, fetched) == (3, T1)
    assert db.execute("SELECT is_complete FROM seasons").fetchone()[0] is True


def test_player_upsert_keeps_match_and_known_fields(db: Any) -> None:
    rec = PlayerRecord("api_football", "5", "M. Akanji", date_of_birth=date(1995, 7, 19))
    repo.upsert_source_players(db, [rec], T0)
    pid = repo.create_player(db)
    repo.set_player_match(db, "api_football", "5", pid, 1.0, "anchor")

    # A later payload without DOB must not erase it or the match.
    repo.upsert_source_players(db, [PlayerRecord("api_football", "5", "Manuel Akanji")], T1)
    row = db.execute(
        "SELECT name, date_of_birth, player_id, matched_by FROM source_players"
    ).fetchone()
    assert row == ("Manuel Akanji", date(1995, 7, 19), pid, "anchor")


def test_market_values_and_transfers_upsert(db: Any) -> None:
    mv = MarketValueRecord("manual", "5", date(2024, 6, 1), 30_000_000, CITY)
    repo.upsert_market_values(db, [mv, mv], T0)
    assert _count(db, "market_values") == 1

    t = TransferRecord(
        "api_football", "5", date(2022, 8, 1), ClubRef("165", "Dortmund"), CITY,
        fee_type="fee", fee_raw="€ 17.5M",
    )  # fmt: skip
    repo.upsert_transfers(db, [t, t], T0)
    assert _count(db, "transfers") == 1


def test_checkpoints_and_usage(db: Any) -> None:
    assert not repo.checkpoint_done(db, "api_football", "players:39:2023:1")
    repo.mark_checkpoint(db, "api_football", "players:39:2023:1", "done", 20)
    assert repo.checkpoint_done(db, "api_football", "players:39:2023:1")

    day = date(2026, 11, 9)
    repo.add_api_usage(db, "api_football", day)
    repo.add_api_usage(db, "api_football", day, 2)
    assert repo.api_usage_on(db, "api_football", day) == 3


def test_integrity_check_flags_orphans(db: Any) -> None:
    from wescout.db.integrity import check_integrity

    repo.upsert_season_stats(db, [_stats()], T0)
    # Stats without a source_players row -> orphan.
    assert check_integrity(db) == {"stats.source_player": 1}
    repo.upsert_source_players(db, [PlayerRecord("api_football", "5", "M. Akanji")], T0)
    assert check_integrity(db) == {}
