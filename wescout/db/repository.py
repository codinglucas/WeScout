"""All writes go through here. Every upsert is idempotent: running the same load twice
leaves the database in the same state (only fetched_at moves forward)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

import duckdb

from wescout.models import (
    ClubRef,
    CompetitionRef,
    License,
    MarketValueRecord,
    PlayerRecord,
    SeasonStatsRecord,
    TransferRecord,
)

Con = duckdb.DuckDBPyConnection


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _one(con: Con, sql: str, params: list[Any]) -> Any:
    row = con.execute(sql, params).fetchone()
    return None if row is None else row[0]


# ---------------------------------------------------------------- reference data


def register_source(
    con: Con, source: str, license: License, attribution: str | None, url: str | None
) -> None:
    con.execute(
        "INSERT INTO sources VALUES (?, ?, ?, ?) ON CONFLICT (source) DO UPDATE SET "
        "license = excluded.license, attribution = excluded.attribution, url = excluded.url",
        [source, license, attribution, url],
    )


def _get_or_create_entity(
    con: Con,
    entity_type: str,
    table: str,
    id_col: str,
    source: str,
    source_id: str,
    insert_cols: dict[str, Any],
    fetched_at: datetime,
) -> int:
    existing = _one(
        con,
        "SELECT entity_id FROM external_ids WHERE entity_type = ? AND source = ? AND source_id = ?",
        [entity_type, source, source_id],
    )
    if existing is not None:
        return int(existing)
    cols = [*insert_cols.keys(), "source", "fetched_at"]
    vals = [*insert_cols.values(), source, fetched_at]
    placeholders = ", ".join("?" for _ in cols)
    new_id = _one(
        con,
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING {id_col}",
        vals,
    )
    con.execute(
        "INSERT INTO external_ids VALUES (?, ?, ?, ?, ?)",
        [entity_type, source, source_id, new_id, fetched_at],
    )
    return int(new_id)


def get_or_create_club(con: Con, source: str, club: ClubRef, fetched_at: datetime) -> int:
    return _get_or_create_entity(
        con, "club", "clubs", "club_id", source, club.source_id,
        {"name": club.name, "country": club.country}, fetched_at,
    )  # fmt: skip


def get_or_create_competition(
    con: Con, source: str, comp: CompetitionRef, fetched_at: datetime
) -> int:
    return _get_or_create_entity(
        con, "competition", "competitions", "competition_id", source, comp.source_id,
        {"name": comp.name, "country": comp.country, "kind": comp.kind}, fetched_at,
    )  # fmt: skip


def get_or_create_season(
    con: Con,
    competition_id: int,
    start_year: int,
    *,
    label: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    is_complete: bool | None = None,
) -> int:
    season_id = _one(
        con,
        "INSERT INTO seasons (competition_id, start_year, label, start_date, end_date, is_complete)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (competition_id, start_year) DO UPDATE SET"
        "  start_date = COALESCE(excluded.start_date, seasons.start_date),"
        "  end_date = COALESCE(excluded.end_date, seasons.end_date),"
        "  is_complete = excluded.is_complete OR seasons.is_complete"
        " RETURNING season_id",
        [
            competition_id,
            start_year,
            label or f"{start_year}/{(start_year + 1) % 100:02d}",
            start_date,
            end_date,
            bool(is_complete),
        ],
    )
    return int(season_id)


# ---------------------------------------------------------------- players


def upsert_source_players(con: Con, players: Iterable[PlayerRecord], fetched_at: datetime) -> int:
    """Insert or refresh source player attributes. Never touches matching columns."""
    n = 0
    for p in players:
        con.execute(
            """
            INSERT INTO source_players (source, source_player_id, name, first_name, last_name,
                date_of_birth, nationality, height_cm, weight_kg, foot, position,
                detailed_position, photo_url, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, source_player_id) DO UPDATE SET
                name = excluded.name,
                first_name = COALESCE(excluded.first_name, source_players.first_name),
                last_name = COALESCE(excluded.last_name, source_players.last_name),
                date_of_birth = COALESCE(excluded.date_of_birth, source_players.date_of_birth),
                nationality = COALESCE(excluded.nationality, source_players.nationality),
                height_cm = COALESCE(excluded.height_cm, source_players.height_cm),
                weight_kg = COALESCE(excluded.weight_kg, source_players.weight_kg),
                foot = COALESCE(excluded.foot, source_players.foot),
                position = COALESCE(excluded.position, source_players.position),
                detailed_position = COALESCE(excluded.detailed_position,
                                             source_players.detailed_position),
                photo_url = COALESCE(excluded.photo_url, source_players.photo_url),
                fetched_at = excluded.fetched_at
            """,
            [
                p.source, p.source_player_id, p.name, p.first_name, p.last_name,
                p.date_of_birth, p.nationality, p.height_cm, p.weight_kg, p.foot, p.position,
                p.detailed_position, p.photo_url, fetched_at,
            ],
        )  # fmt: skip
        n += 1
    return n


def create_player(con: Con) -> int:
    return int(_one(con, "INSERT INTO players DEFAULT VALUES RETURNING player_id", []))


def set_player_match(
    con: Con,
    source: str,
    source_player_id: str,
    player_id: int,
    confidence: float,
    matched_by: str,
) -> None:
    con.execute(
        "UPDATE source_players SET player_id = ?, match_confidence = ?, matched_by = ?"
        " WHERE source = ? AND source_player_id = ?",
        [player_id, confidence, matched_by, source, source_player_id],
    )
    con.execute(
        "DELETE FROM match_reviews WHERE source = ? AND source_player_id = ?",
        [source, source_player_id],
    )


def add_match_review(
    con: Con,
    source: str,
    source_player_id: str,
    candidate_player_id: int | None,
    score: float,
    reason: str,
) -> None:
    con.execute(
        "INSERT INTO match_reviews (source, source_player_id, candidate_player_id, score, reason)"
        " VALUES (?, ?, ?, ?, ?) ON CONFLICT (source, source_player_id) DO UPDATE SET"
        " candidate_player_id = excluded.candidate_player_id, score = excluded.score,"
        " reason = excluded.reason, created_at = current_timestamp",
        [source, source_player_id, candidate_player_id, score, reason],
    )


# ---------------------------------------------------------------- facts


_STAT_COLS = (
    "position", "appearances", "starts", "minutes", "rating", "goals", "assists",
    "key_passes", "tackles", "interceptions", "dribbled_past", "big_chances_created",
    "accurate_passes", "total_passes",
)  # fmt: skip


def upsert_season_stats(
    con: Con,
    rows: Iterable[SeasonStatsRecord],
    fetched_at: datetime,
    *,
    season_complete: bool = False,
) -> int:
    n = 0
    for r in rows:
        comp_id = get_or_create_competition(con, r.source, r.competition, fetched_at)
        club_id = get_or_create_club(con, r.source, r.club, fetched_at)
        season_id = get_or_create_season(
            con, comp_id, r.season_start_year, is_complete=season_complete
        )
        values = [getattr(r, c) for c in _STAT_COLS]
        updates = ", ".join(f"{c} = excluded.{c}" for c in _STAT_COLS)
        cols = ", ".join(_STAT_COLS)
        placeholders = ", ".join("?" for _ in range(len(_STAT_COLS) + 6))
        con.execute(
            f"INSERT INTO player_season_stats (source, source_player_id, season_id, club_id,"
            f" {cols}, extra, fetched_at) VALUES ({placeholders})"
            f" ON CONFLICT (source, source_player_id, season_id, club_id) DO UPDATE SET"
            f" {updates}, extra = excluded.extra, fetched_at = excluded.fetched_at",
            [
                r.source, r.source_player_id, season_id, club_id, *values,
                json.dumps(r.extra, sort_keys=True), fetched_at,
            ],
        )  # fmt: skip
        n += 1
    return n


def upsert_market_values(con: Con, rows: Iterable[MarketValueRecord], fetched_at: datetime) -> int:
    n = 0
    for r in rows:
        club_id = get_or_create_club(con, r.source, r.club, fetched_at) if r.club else None
        con.execute(
            "INSERT INTO market_values VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (source, source_player_id, valued_at) DO UPDATE SET"
            " value_eur = excluded.value_eur, club_id = excluded.club_id,"
            " fetched_at = excluded.fetched_at",
            [r.source, r.source_player_id, r.valued_at, r.value_eur, club_id, fetched_at],
        )
        n += 1
    return n


def upsert_transfers(con: Con, rows: Iterable[TransferRecord], fetched_at: datetime) -> int:
    n = 0
    for r in rows:
        from_id = (
            get_or_create_club(con, r.source, r.from_club, fetched_at) if r.from_club else None
        )
        to_id = get_or_create_club(con, r.source, r.to_club, fetched_at) if r.to_club else None
        con.execute(
            "INSERT INTO transfers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (source, source_player_id, transfer_key) DO UPDATE SET"
            " fee_eur = excluded.fee_eur, fee_type = excluded.fee_type,"
            " fee_raw = excluded.fee_raw, fetched_at = excluded.fetched_at",
            [
                r.source, r.source_player_id, r.transfer_key, r.transfer_date, from_id, to_id,
                r.fee_eur, r.fee_type, r.fee_raw, fetched_at,
            ],
        )  # fmt: skip
        n += 1
    return n


# ---------------------------------------------------------------- ETL bookkeeping


def start_run(con: Con, provider: str, args: dict[str, Any]) -> int:
    return int(
        _one(
            con,
            "INSERT INTO etl_runs (provider, args, started_at, status) VALUES (?, ?, ?, 'running')"
            " RETURNING run_id",
            [provider, json.dumps(args, sort_keys=True), utcnow()],
        )
    )


def finish_run(
    con: Con, run_id: int, status: str, records: int, requests_used: int, message: str = ""
) -> None:
    con.execute(
        "UPDATE etl_runs SET finished_at = ?, status = ?, records = ?, requests_used = ?,"
        " message = ? WHERE run_id = ?",
        [utcnow(), status, records, requests_used, message, run_id],
    )


def checkpoint_done(con: Con, provider: str, task_key: str) -> bool:
    return (
        _one(
            con,
            "SELECT 1 FROM etl_checkpoints WHERE provider = ? AND task_key = ? AND status = 'done'",
            [provider, task_key],
        )
        is not None
    )


def mark_checkpoint(con: Con, provider: str, task_key: str, status: str, records: int) -> None:
    con.execute(
        "INSERT INTO etl_checkpoints VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (provider, task_key) DO UPDATE SET status = excluded.status,"
        " records = excluded.records, updated_at = excluded.updated_at",
        [provider, task_key, status, records, utcnow()],
    )


def add_api_usage(con: Con, provider: str, day: date, n: int = 1) -> None:
    con.execute(
        "INSERT INTO api_usage VALUES (?, ?, ?) ON CONFLICT (provider, usage_date)"
        " DO UPDATE SET requests_used = api_usage.requests_used + excluded.requests_used",
        [provider, day, n],
    )


def api_usage_on(con: Con, provider: str, day: date) -> int:
    v = _one(
        con,
        "SELECT requests_used FROM api_usage WHERE provider = ? AND usage_date = ?",
        [provider, day],
    )
    return int(v or 0)


def record_raw_response(
    con: Con,
    request_key: str,
    source: str,
    endpoint: str,
    params: dict[str, Any],
    path: str,
    status_code: int,
    fetched_at: datetime,
) -> None:
    con.execute(
        "INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (request_key)"
        " DO UPDATE SET path = excluded.path, status_code = excluded.status_code,"
        " fetched_at = excluded.fetched_at",
        [request_key, source, endpoint, json.dumps(params, sort_keys=True), path, status_code,
         fetched_at],
    )  # fmt: skip
