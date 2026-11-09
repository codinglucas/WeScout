"""Referential-integrity checks (DuckDB FKs block upserts, so we check after loads)."""

from __future__ import annotations

import duckdb

# name -> query returning the number of orphan rows
CHECKS: dict[str, str] = {
    "stats.season": "SELECT count(*) FROM player_season_stats s"
    " LEFT JOIN seasons x USING (season_id) WHERE x.season_id IS NULL",
    "stats.club": "SELECT count(*) FROM player_season_stats s"
    " LEFT JOIN clubs c USING (club_id) WHERE c.club_id IS NULL",
    "stats.source_player": "SELECT count(*) FROM player_season_stats s"
    " LEFT JOIN source_players p USING (source, source_player_id) WHERE p.name IS NULL",
    "stats.source": "SELECT count(*) FROM player_season_stats s"
    " LEFT JOIN sources x USING (source) WHERE x.license IS NULL",
    "source_players.player": "SELECT count(*) FROM source_players s"
    " LEFT JOIN players p USING (player_id)"
    " WHERE s.player_id IS NOT NULL AND p.player_id IS NULL",
    "source_players.source": "SELECT count(*) FROM source_players s"
    " LEFT JOIN sources x USING (source) WHERE x.license IS NULL",
    "seasons.competition": "SELECT count(*) FROM seasons s"
    " LEFT JOIN competitions c USING (competition_id) WHERE c.competition_id IS NULL",
    "market_values.source": "SELECT count(*) FROM market_values s"
    " LEFT JOIN sources x USING (source) WHERE x.license IS NULL",
}


def check_integrity(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return {check_name: orphan_count} for every failing check (empty dict = all good)."""
    failures: dict[str, int] = {}
    for name, sql in CHECKS.items():
        row = con.execute(sql).fetchone()
        n = int(row[0]) if row else 0
        if n:
            failures[name] = n
    return failures
