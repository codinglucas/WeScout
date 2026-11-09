"""Player detail and catalogue metadata. Same PUBLIC_MODE rule as search: every query joins
the `allowed` sources, so a public response never contains local-only data."""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb

from wescout.api.search import SOURCE_PRIORITY_SQL, season_label, sofascore_ratings

PER90_KEYS = ("goals", "assists", "key_passes", "tackles", "interceptions", "total_passes")

ALLOWED = "SELECT source FROM sources WHERE NOT $public OR license <> 'local_scrape'"

PLAYER_SQL = f"""
WITH allowed AS ({ALLOWED})
SELECT sp.player_id,
       arg_min(sp.name, {SOURCE_PRIORITY_SQL}) AS name,
       arg_min(sp.first_name, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.first_name IS NOT NULL) AS first_name,
       arg_min(sp.last_name, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.last_name IS NOT NULL) AS last_name,
       arg_min(sp.date_of_birth, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.date_of_birth IS NOT NULL) AS date_of_birth,
       arg_min(sp.nationality, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.nationality IS NOT NULL) AS nationality,
       arg_min(sp.height_cm, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.height_cm IS NOT NULL) AS height_cm,
       arg_min(sp.weight_kg, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.weight_kg IS NOT NULL) AS weight_kg,
       arg_min(sp.position, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.position IS NOT NULL) AS position,
       arg_min(sp.detailed_position, {SOURCE_PRIORITY_SQL})
           FILTER (WHERE sp.detailed_position IS NOT NULL) AS detailed_position
FROM source_players sp JOIN allowed USING (source)
WHERE sp.player_id = $player_id
GROUP BY sp.player_id
"""

SEASONS_SQL = f"""
WITH allowed AS ({ALLOWED}),
rows AS (
    SELECT s.*, x.start_year, cp.name AS competition, c.name AS club,
           {SOURCE_PRIORITY_SQL} AS priority
    FROM player_season_stats s
    JOIN allowed USING (source)
    JOIN source_players sp USING (source, source_player_id)
    JOIN seasons x USING (season_id)
    JOIN competitions cp USING (competition_id)
    JOIN clubs c USING (club_id)
    WHERE sp.player_id = $player_id
)
SELECT start_year, competition, club, position, appearances, starts, minutes, rating, goals,
       assists, key_passes, tackles, interceptions, dribbled_past, total_passes
FROM rows
QUALIFY priority = min(priority) OVER (PARTITION BY start_year)  -- one source per season
ORDER BY start_year DESC, minutes DESC NULLS LAST
"""

TRANSFERS_SQL = f"""
WITH allowed AS ({ALLOWED})
SELECT t.transfer_date, f.name AS from_club, d.name AS to_club, t.fee_eur, t.fee_type, t.fee_raw
FROM transfers t
JOIN allowed USING (source)
JOIN source_players sp USING (source, source_player_id)
LEFT JOIN clubs f ON f.club_id = t.from_club_id
LEFT JOIN clubs d ON d.club_id = t.to_club_id
WHERE sp.player_id = $player_id
ORDER BY t.transfer_date DESC NULLS LAST
"""


def _age(dob: date | None, today: date) -> int | None:
    if dob is None:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _per90(count: Any, minutes: Any) -> float | None:
    if count is None or not minutes:
        return None
    return round(float(count) * 90 / float(minutes), 2)


def _rows(cur: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, values, strict=True)) for values in cur.fetchall()]


def player_detail(
    con: duckdb.DuckDBPyConnection, player_id: int, *, public: bool
) -> dict[str, Any] | None:
    cur = con.cursor()
    params = {"public": public, "player_id": player_id}
    found = _rows(cur.execute(PLAYER_SQL, params))
    if not found:
        return None
    p = found[0]
    seasons = []
    for r in _rows(cur.execute(SEASONS_SQL, params)):
        seasons.append(
            {
                "season": season_label(r["start_year"]),
                "start_year": r["start_year"],
                "competition": r["competition"],
                "club": r["club"],
                "position_group": r["position"],
                "appearances": r["appearances"],
                "starts": r["starts"],
                "minutes": r["minutes"],
                "rating": round(r["rating"], 2) if r["rating"] is not None else None,
                "goals": r["goals"],
                "assists": r["assists"],
                "key_passes": r["key_passes"],
                "tackles": r["tackles"],
                "interceptions": r["interceptions"],
                "dribbled_past": r["dribbled_past"],
                "total_passes": r["total_passes"],
                "per90": {k: _per90(r[k], r["minutes"]) for k in PER90_KEYS},
            }
        )
    transfers = [
        {
            "date": r["transfer_date"].isoformat() if r["transfer_date"] else None,
            "from_club": r["from_club"],
            "to_club": r["to_club"],
            "fee_eur": r["fee_eur"],
            "fee_type": r["fee_type"],
            "fee_raw": r["fee_raw"],
        }
        for r in _rows(cur.execute(TRANSFERS_SQL, params))
    ]
    ratings = [] if public else sofascore_ratings(cur, [player_id]).get(player_id, [])
    dob = p["date_of_birth"]
    return {
        "player_id": p["player_id"],
        "name": p["name"],
        "full_name": " ".join(x for x in (p["first_name"], p["last_name"]) if x) or p["name"],
        "date_of_birth": dob.isoformat() if dob else None,
        "age": _age(dob, date.today()),
        "nationality": p["nationality"],
        "height_cm": p["height_cm"],
        "weight_kg": p["weight_kg"],
        "position_group": p["position"],
        "position": (p["detailed_position"] or p["position"] or "").upper() or None,
        "seasons": seasons,
        "transfers": transfers,
        "sofascore_ratings": ratings,
    }


def catalogue(con: duckdb.DuckDBPyConnection, *, public: bool) -> dict[str, Any]:
    cur = con.cursor()
    comps = _rows(
        cur.execute(
            f"""
            WITH allowed AS ({ALLOWED})
            SELECT cp.competition_id, cp.name, cp.country, x.start_year,
                   count(DISTINCT sp.player_id) AS players, count(DISTINCT s.club_id) AS clubs
            FROM player_season_stats s
            JOIN allowed USING (source)
            JOIN source_players sp USING (source, source_player_id)
            JOIN seasons x USING (season_id)
            JOIN competitions cp USING (competition_id)
            WHERE sp.player_id IS NOT NULL
            GROUP BY ALL ORDER BY players DESC
            """,
            {"public": public},
        )
    )
    seasons = sorted({c["start_year"] for c in comps}, reverse=True)
    competitions: dict[int, dict[str, Any]] = {}
    for c in comps:
        entry = competitions.setdefault(
            c["competition_id"],
            {"id": c["competition_id"], "name": c["name"], "country": c["country"],
             "seasons": []},
        )  # fmt: skip
        entry["seasons"].append(
            {"season": c["start_year"], "players": c["players"], "clubs": c["clubs"]}
        )
    return {
        "seasons": [{"start_year": s, "label": season_label(s)} for s in seasons],
        "competitions": list(competitions.values()),
    }
