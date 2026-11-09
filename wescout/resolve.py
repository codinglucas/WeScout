"""Assign canonical player_ids to source_players rows.

Order: (1) the anchor source (API-Football) gets one canonical player per source ID,
(2) manual overrides, (3) fuzzy matching for everything else -> auto / review / new.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from wescout.db import repository as repo
from wescout.matching import MatchSubject, core_tokens, load_manual_matches, match_subject

log = logging.getLogger(__name__)
ANCHOR_SOURCE = "api_football"


@dataclass
class ResolveStats:
    anchored: int = 0
    manual: int = 0
    auto: int = 0
    review: int = 0
    new: int = 0


def _clubs_by_source_player(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], set[str]]:
    rows = con.execute(
        """
        SELECT s.source, s.source_player_id, c.name FROM player_season_stats s
        JOIN clubs c USING (club_id)
        UNION
        SELECT m.source, m.source_player_id, c.name FROM market_values m
        JOIN clubs c USING (club_id)
        """
    ).fetchall()
    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, spid, club in rows:
        out[(source, spid)].add(club)
    return out


def _subject(row: tuple[object, ...], clubs: set[str], key: str) -> MatchSubject:
    _, _, name, first, last, dob = row[:6]
    return MatchSubject.build(
        key,
        str(name),
        first_name=str(first) if first else None,
        last_name=str(last) if last else None,
        date_of_birth=dob if isinstance(dob, date) else None,
        clubs=clubs,
    )


def resolve_players(
    con: duckdb.DuckDBPyConnection, manual_path: Path | None = None
) -> ResolveStats:
    stats = ResolveStats()

    # 1. Anchors.
    for (spid,) in con.execute(
        "SELECT source_player_id FROM source_players WHERE source = ? AND player_id IS NULL",
        [ANCHOR_SOURCE],
    ).fetchall():
        repo.set_player_match(con, ANCHOR_SOURCE, spid, repo.create_player(con), 1.0, "anchor")
        stats.anchored += 1

    # 2. Manual overrides (always win, also over earlier automatic matches).
    for m in load_manual_matches(manual_path) if manual_path else []:
        if m.match_source is None:
            target = repo.create_player(con)
        else:
            row = con.execute(
                "SELECT player_id FROM source_players WHERE source = ? AND source_player_id = ?",
                [m.match_source, m.match_source_player_id],
            ).fetchone()
            if row is None or row[0] is None:
                log.warning("manual match target not found: %s", m)
                continue
            target = int(row[0])
        repo.set_player_match(con, m.source, m.source_player_id, target, 1.0, "manual")
        stats.manual += 1

    # 3. Fuzzy matching for the rest.
    pending = con.execute(
        "SELECT source, source_player_id, name, first_name, last_name, date_of_birth"
        " FROM source_players WHERE player_id IS NULL AND source <> ?",
        [ANCHOR_SOURCE],
    ).fetchall()
    if not pending:
        return stats

    clubs = _clubs_by_source_player(con)
    anchors = con.execute(
        "SELECT source, source_player_id, name, first_name, last_name, date_of_birth, player_id"
        " FROM source_players WHERE source = ? AND player_id IS NOT NULL",
        [ANCHOR_SOURCE],
    ).fetchall()
    # Blocking: index candidates by DOB (and swapped DOB) and by last-name token.
    by_dob: dict[date, list[MatchSubject]] = defaultdict(list)
    by_token: dict[str, list[MatchSubject]] = defaultdict(list)
    for row in anchors:
        subj = _subject(row, clubs.get((row[0], row[1]), set()), str(row[6]))
        if subj.date_of_birth:
            by_dob[subj.date_of_birth].append(subj)
        for token in {_last_token(n) for n in subj.names} - {""}:
            by_token[token].append(subj)

    for row in pending:
        source, spid = str(row[0]), str(row[1])
        subj = _subject(row, clubs.get((source, spid), set()), f"{source}:{spid}")
        candidates: dict[str, MatchSubject] = {}
        if subj.date_of_birth:
            dob = subj.date_of_birth
            keys = [dob]
            if dob.day <= 12:
                keys.append(date(dob.year, dob.day, dob.month))
            for k in keys:
                candidates.update({c.key: c for c in by_dob.get(k, [])})
        else:
            for n in subj.names:
                candidates.update({c.key: c for c in by_token.get(_last_token(n), [])})
        result = match_subject(subj, candidates.values())
        if result.decision == "auto" and result.candidate is not None:
            repo.set_player_match(con, source, spid, int(result.candidate), result.score, "auto")
            stats.auto += 1
        elif result.decision == "review":
            repo.add_match_review(
                con, source, spid,
                int(result.candidate) if result.candidate else None, result.score, result.reason,
            )  # fmt: skip
            stats.review += 1
        else:
            repo.set_player_match(con, source, spid, repo.create_player(con), result.score, "new")
            stats.new += 1
    return stats


def _last_token(name: str) -> str:
    tokens = core_tokens(name)
    return tokens[-1] if tokens else ""
