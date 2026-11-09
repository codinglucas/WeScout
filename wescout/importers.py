"""Import hand-collected season ratings from a CSV file (local-only data).

    uv run python -m wescout.etl --import-sofascore data/sofascore_ratings.csv

CSV columns (header required; extra columns ignored):
    player_name, club, season, rating, minutes        - required: player_name, season, rating
    date_of_birth (YYYY-MM-DD), sofascore_id          - optional, improve matching

One row = one player, one season, one club, rating across all competitions.
`season` accepts "2023/24", "23/24" or "2023" (start year).

WeScout never fetches these ratings itself; it only reads the file. Rows are stored with a
local_scrape source, so they are hidden in PUBLIC_MODE and never used for models.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import duckdb

from wescout.db import repository as repo
from wescout.matching import (
    AUTO,
    MatchSubject,
    club_score,
    match_subject,
    name_score,
    normalize_name,
)
from wescout.models import PlayerRecord

log = logging.getLogger(__name__)

SOFASCORE_MANUAL = "sofascore_manual"
ANCHOR_SOURCE = "api_football"
NAME_ONLY_MARGIN = 0.10  # best name must beat the runner-up in that club by this much


class CsvFormatError(ValueError):
    pass


@dataclass
class ImportStats:
    rows: int = 0
    players: int = 0
    matched: int = 0
    review: int = 0
    skipped_rows: list[str] = field(default_factory=list)


@dataclass
class _Row:
    line: int
    name: str
    club: str
    season: int
    rating: float
    minutes: int | None


@dataclass
class _Player:
    name: str
    dob: date | None
    sofascore_id: str | None
    rows: list[_Row] = field(default_factory=list)

    @property
    def clubs(self) -> set[str]:
        return {r.club for r in self.rows if r.club}

    @property
    def source_player_id(self) -> str:
        if self.sofascore_id:
            return self.sofascore_id
        key = normalize_name(self.name).replace(" ", "-")
        return f"{key}:{self.dob.isoformat()}" if self.dob else key


def parse_season(text: str) -> int:
    """'2023/24' -> 2023, '23/24' -> 2023, '2023' -> 2023, '2023-24' -> 2023."""
    first = text.strip().replace("-", "/").split("/")[0].strip()
    if not first.isdigit():
        raise ValueError(f"bad season '{text}'")
    year = int(first)
    return year + 2000 if year < 100 else year


def read_ratings_csv(path: Path) -> tuple[list[_Player], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        lines = fh.readlines()
    # Comment lines ('#') are allowed before the header; keep real line numbers in messages.
    offset = next((i for i, line in enumerate(lines) if not line.startswith("#")), len(lines))
    reader = csv.DictReader(lines[offset:])
    header = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = {"player_name", "season", "rating"} - header
    if missing:
        raise CsvFormatError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
    players: dict[tuple[str, date | None, str | None], _Player] = {}
    skipped: list[str] = []
    for line_no, raw in enumerate(reader, start=offset + 2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            name = row["player_name"]
            if not name:
                raise ValueError("empty player_name")
            dob = date.fromisoformat(row["date_of_birth"]) if row.get("date_of_birth") else None
            rating = float(row["rating"].replace(",", "."))
            if not 0 < rating <= 10:
                raise ValueError(f"rating {rating} outside 0-10")
            minutes = int(float(row["minutes"])) if row.get("minutes") else None
            season = parse_season(row["season"])
        except (ValueError, KeyError) as exc:
            skipped.append(f"line {line_no}: {exc}")
            continue
        sid = row.get("sofascore_id") or None
        key = (normalize_name(name), dob, sid)
        player = players.setdefault(key, _Player(name, dob, sid))
        player.rows.append(_Row(line_no, name, row.get("club", ""), season, rating, minutes))
    return list(players.values()), skipped


def _anchor_candidates(
    con: duckdb.DuckDBPyConnection,
) -> list[tuple[int, str, str | None, str | None, date | None, set[str]]]:
    rows = con.execute(
        """
        SELECT sp.player_id, sp.name, sp.first_name, sp.last_name, sp.date_of_birth,
               list(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL)
        FROM source_players sp
        LEFT JOIN player_season_stats s USING (source, source_player_id)
        LEFT JOIN clubs c USING (club_id)
        WHERE sp.source = ? AND sp.player_id IS NOT NULL
        GROUP BY ALL
        """,
        [ANCHOR_SOURCE],
    ).fetchall()
    return [(r[0], r[1], r[2], r[3], r[4], set(r[5] or [])) for r in rows]


def _match_by_name_and_club(
    player: _Player,
    candidates: list[tuple[int, str, str | None, str | None, date | None, set[str]]],
) -> tuple[int | None, float, str, bool]:
    """No DOB: only accept when the name clearly identifies one player of the same club."""
    clubs = frozenset(normalize_name(c) for c in player.clubs)
    scored = []
    for pid, name, first, last, _dob, cand_clubs in candidates:
        if club_score(clubs, frozenset(normalize_name(c) for c in cand_clubs)) < 0.85:
            continue
        subject = MatchSubject.build(str(pid), name, first, last)
        scored.append((name_score((player.name,), subject.names), pid, name))
    if not scored:
        return None, 0.0, "no player from that club in the database", False
    scored.sort(reverse=True)
    best, pid, best_name = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    reason = f"name={best:.2f} vs {best_name}; next={runner_up:.2f}; same club"
    if best >= AUTO and best - runner_up >= NAME_ONLY_MARGIN:
        # Capped below 1.0: without a DOB this is never as certain as a DOB match.
        return pid, round(min(best, 0.95), 4), reason, True
    return (pid if best >= 0.7 else None), round(best, 4), reason, False


def import_ratings_csv(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    *,
    source: str = SOFASCORE_MANUAL,
    attribution: str | None = None,
) -> ImportStats:
    players, skipped = read_ratings_csv(path)
    stats = ImportStats(rows=sum(len(p.rows) for p in players), players=len(players))
    stats.skipped_rows = skipped
    fetched: datetime = repo.utcnow()
    repo.register_source(con, source, "local_scrape", attribution, None)
    candidates = _anchor_candidates(con)
    by_dob: dict[date, list[MatchSubject]] = defaultdict(list)
    for cand_id, name, first, last, dob, clubs in candidates:
        if dob:
            by_dob[dob].append(MatchSubject.build(str(cand_id), name, first, last, dob, clubs))

    con.execute("BEGIN")
    try:
        for p in players:
            spid = p.source_player_id
            repo.upsert_source_players(
                con, [PlayerRecord(source, spid, p.name, date_of_birth=p.dob)], fetched
            )
            # Replace this player's rows so edits/removals in the CSV are reflected.
            con.execute(
                "DELETE FROM player_season_ratings WHERE source = ? AND source_player_id = ?",
                [source, spid],
            )
            totals: dict[tuple[int, str], _Row] = {}
            for r in p.rows:
                totals[(r.season, r.club)] = r  # last row wins for duplicates
            for (season, club), r in totals.items():
                con.execute(
                    "INSERT INTO player_season_ratings (source, source_player_id,"
                    " season_start_year, club_name, rating, minutes, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [source, spid, season, club, r.rating, r.minutes, fetched],
                )

            already = con.execute(
                "SELECT matched_by FROM source_players WHERE source = ? AND source_player_id = ?"
                " AND player_id IS NOT NULL",
                [source, spid],
            ).fetchone()
            if already is not None and already[0] == "manual":
                stats.matched += 1
                continue  # never override a manual decision

            pid: int | None
            if p.dob is not None:
                subject = MatchSubject.build(f"{source}:{spid}", p.name, date_of_birth=p.dob,
                                             clubs=p.clubs)  # fmt: skip
                pool = by_dob.get(p.dob, [])
                result = match_subject(subject, pool)
                pid = int(result.candidate) if result.candidate else None
                ok, score, reason = result.decision == "auto", result.score, result.reason
            else:
                pid, score, reason, ok = _match_by_name_and_club(p, candidates)

            if ok and pid is not None:
                repo.set_player_match(con, source, spid, pid, score, "auto")
                stats.matched += 1
            else:
                con.execute(
                    "UPDATE source_players SET player_id = NULL WHERE source = ?"
                    " AND source_player_id = ?",
                    [source, spid],
                )
                repo.add_match_review(con, source, spid, pid, score, reason)
                stats.review += 1
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    for msg in skipped:
        log.warning("skipped %s", msg)
    return stats
