"""Player search: one SQL query against DuckDB. No provider or scraper is ever called here.

PUBLIC_MODE is enforced in SQL: every table that carries data is joined to the `allowed`
set of sources (license <> 'local_scrape'), so scraped rows can't leak into any field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from wescout.models import DETAILED_TO_COARSE

# Lower = preferred when two sources describe the same player-season.
SOURCE_PRIORITY_SQL = "CASE source WHEN 'api_football' THEN 1 WHEN 'statsbomb' THEN 2 ELSE 9 END"


@dataclass(frozen=True)
class SearchParams:
    min_age: int | None = None
    max_age: int | None = None
    min_value: int | None = None
    max_value: int | None = None
    position: str | None = None
    season: int | None = None
    min_minutes: int = 0
    limit: int = 50


SEARCH_SQL = f"""
WITH allowed AS (
    SELECT source FROM sources WHERE NOT $public OR license <> 'local_scrape'
),
season_rows AS (
    SELECT sp.player_id, s.source, s.club_id, s.minutes, s.appearances, s.rating, s.goals,
           s.assists, s.key_passes, s.tackles, s.interceptions, s.dribbled_past,
           s.big_chances_created, s.accurate_passes, s.total_passes, s.position,
           {SOURCE_PRIORITY_SQL} AS priority
    FROM player_season_stats s
    JOIN allowed USING (source)
    JOIN source_players sp USING (source, source_player_id)
    JOIN seasons x USING (season_id)
    WHERE sp.player_id IS NOT NULL AND x.start_year = $season
),
best_source AS (   -- one source per player, so stats are never double counted
    SELECT player_id, arg_min(source, priority) AS source FROM season_rows GROUP BY player_id
),
season_stats AS (  -- sum across clubs (mid-season transfers); rating weighted by minutes
    SELECT r.player_id,
           sum(r.minutes) AS minutes, sum(r.appearances) AS appearances,
           sum(r.rating * r.minutes) / nullif(sum(CASE WHEN r.rating IS NOT NULL
               THEN r.minutes END), 0) AS rating,
           sum(r.goals) AS goals, sum(r.assists) AS assists, sum(r.key_passes) AS key_passes,
           sum(r.tackles) AS tackles, sum(r.interceptions) AS interceptions,
           sum(r.dribbled_past) AS dribbled_past,
           sum(r.big_chances_created) AS big_chances_created,
           sum(r.accurate_passes) AS accurate_passes, sum(r.total_passes) AS total_passes,
           arg_max(c.name, coalesce(r.minutes, 0)) AS club_name,
           arg_max(r.position, coalesce(r.minutes, 0)) AS season_position
    FROM season_rows r
    JOIN best_source b USING (player_id, source)
    JOIN clubs c USING (club_id)
    GROUP BY r.player_id
),
attrs AS (         -- player attributes from allowed sources only, best source first
    SELECT sp.player_id,
           arg_min(sp.name, {SOURCE_PRIORITY_SQL}) AS name,
           arg_min(sp.date_of_birth, {SOURCE_PRIORITY_SQL})
               FILTER (WHERE sp.date_of_birth IS NOT NULL) AS date_of_birth,
           arg_min(sp.nationality, {SOURCE_PRIORITY_SQL})
               FILTER (WHERE sp.nationality IS NOT NULL) AS nationality,
           arg_min(sp.position, {SOURCE_PRIORITY_SQL})
               FILTER (WHERE sp.position IS NOT NULL) AS position,
           arg_min(sp.detailed_position, {SOURCE_PRIORITY_SQL})
               FILTER (WHERE sp.detailed_position IS NOT NULL) AS detailed_position
    FROM source_players sp
    JOIN allowed USING (source)
    WHERE sp.player_id IS NOT NULL
    GROUP BY sp.player_id
),
latest_value AS (
    SELECT sp.player_id, arg_max(m.value_eur, m.valued_at) AS value_eur,
           max(m.valued_at) AS valued_at
    FROM market_values m
    JOIN allowed USING (source)
    JOIN source_players sp USING (source, source_player_id)
    WHERE sp.player_id IS NOT NULL
    GROUP BY sp.player_id
)
SELECT st.player_id, a.name, st.club_name, a.nationality, a.date_of_birth,
       date_diff('year', a.date_of_birth, current_date)
           - CASE WHEN strftime(current_date, '%m%d') < strftime(a.date_of_birth, '%m%d')
                  THEN 1 ELSE 0 END AS age,
       coalesce(a.position, st.season_position) AS position,
       a.detailed_position,
       v.value_eur, v.valued_at,
       st.minutes, st.appearances, st.rating, st.goals, st.assists, st.key_passes,
       st.tackles, st.interceptions, st.dribbled_past, st.big_chances_created,
       st.accurate_passes, st.total_passes
FROM season_stats st
JOIN attrs a USING (player_id)
LEFT JOIN latest_value v USING (player_id)
WHERE coalesce(st.minutes, 0) >= $min_minutes
  AND ($min_age IS NULL OR age >= $min_age)
  AND ($max_age IS NULL OR age <= $max_age)
  -- Value filters only apply where a value is known (none in PUBLIC_MODE today).
  AND ($min_value IS NULL OR v.value_eur IS NULL OR v.value_eur >= $min_value)
  AND ($max_value IS NULL OR v.value_eur IS NULL OR v.value_eur <= $max_value)
  AND ($detailed IS NULL
       OR a.detailed_position = $detailed
       OR (a.detailed_position IS NULL AND coalesce(a.position, st.season_position) = $coarse))
ORDER BY st.rating DESC NULLS LAST, st.minutes DESC NULLS LAST, st.player_id
LIMIT $limit
"""


def latest_season(con: duckdb.DuckDBPyConnection, public: bool) -> int | None:
    row = con.execute(
        "SELECT max(x.start_year) FROM player_season_stats s JOIN seasons x USING (season_id)"
        " JOIN sources USING (source) WHERE NOT ? OR license <> 'local_scrape'",
        [public],
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def format_value(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000:
        return f"€{value / 1_000_000:.2f}m"
    return f"€{value // 1_000}k"


def _per90(count: Any, minutes: Any) -> float | None:
    if count is None or not minutes:
        return None
    return round(float(count) * 90 / float(minutes), 2)


def search_players(
    con: duckdb.DuckDBPyConnection, params: SearchParams, *, public: bool
) -> tuple[list[dict[str, Any]], int | None]:
    season = params.season or latest_season(con, public)
    if season is None:
        return [], None
    detailed = (params.position or "").lower() or None
    cursor = con.cursor()
    rows = cursor.execute(
        SEARCH_SQL,
        {
            "public": public,
            "season": season,
            "min_minutes": params.min_minutes,
            "min_age": params.min_age,
            "max_age": params.max_age,
            "min_value": params.min_value,
            "max_value": params.max_value,
            "detailed": detailed,
            "coarse": DETAILED_TO_COARSE.get(detailed or ""),
            "limit": params.limit,
        },
    )
    columns = [d[0] for d in rows.description]
    out = []
    for values in rows.fetchall():
        r = dict(zip(columns, values, strict=True))
        minutes = r["minutes"]
        accurate, total = r["accurate_passes"], r["total_passes"]
        out.append(
            {
                # Response shape kept from the legacy Flask API (dashboard.js / lists.js).
                "player_id": r["player_id"],
                "player_name": r["name"],
                "club_name": r["club_name"],
                "position": (r["detailed_position"] or r["position"] or "").upper() or None,
                "age": r["age"],
                "nationality": r["nationality"],
                "price": format_value(r["value_eur"]),
                "price_int": r["value_eur"],
                "rating": round(r["rating"], 2) if r["rating"] is not None else None,
                "goals": r["goals"],
                "assists": r["assists"],
                "key_passes": r["key_passes"],
                "minutes_played": minutes,
                "appearances": r["appearances"],
                "tackles": r["tackles"],
                "interceptions": r["interceptions"],
                "dribbled_past": r["dribbled_past"],
                "big_chances_created": r["big_chances_created"],
                "accurate_passes": accurate,
                "total_passes": total,
                "tackles_per_90": _per90(r["tackles"], minutes),
                "interceptions_per_90": _per90(r["interceptions"], minutes),
                "dribbled_past_per_90": _per90(r["dribbled_past"], minutes),
                "pass_completion": round(accurate * 100 / total, 1)
                if accurate is not None and total
                else None,
            }
        )
    return out, season


def attributions(con: duckdb.DuckDBPyConnection, public: bool) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT attribution FROM sources JOIN player_season_stats USING (source)"
        " WHERE attribution IS NOT NULL AND (NOT ? OR license <> 'local_scrape') ORDER BY 1",
        [public],
    ).fetchall()
    return [r[0] for r in rows]
