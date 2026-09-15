"""
Final version.

Two tiers of attributes:

  - Z-SCORED (8 attributes): rating, goals, assists, keyPasses, tackles,
    interceptions, bigChancesCreated, accuratePasses. These are confirmed
    reachable via the tournament statistics endpoint (group=defence /
    group=passing), so each player's raw value is converted to a z-score
    against that season's league distribution before being accumulated.

  - RAW SUM (4 attributes): appearances, minutesPlayed, dribbledPast,
    totalPasses. Not reachable via the bulk statistics endpoint (only
    exist under "detailed" groups whose query param isn't confirmed), so
    these keep the original behavior: summed directly from the per-player
    statistics/overall endpoint, same as your very first version.
"""

import time
import json
import os
import pandas as pd
from selenium import webdriver
from sofascore import execute, fetch_json

# --- League baseline (z-scored attributes only) ----------------------------

_league_stats_cache = {}
_LEAGUE_CACHE_FILE = "league_stats_cache.json"

ZSCORE_STAT_TO_ATTR = {
    "rating": "rating",
    "goals": "goals",
    "assists": "assists",
    "keyPasses": "key_passes",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "bigChancesCreated": "big_chances_created",
    "accuratePasses": "accurate_passes",
}

# Fields that only exist as raw totals — no league baseline available.
RAW_SUM_STAT_TO_ATTR = {
    "appearances": "matches",
    "minutesPlayed": "minutes_played",
    "dribbledPast": "dribbled_past",
    "totalPasses": "total_passes",
}

GROUPS_TO_QUERY = ["defence", "passing"]  # covers every ZSCORE_STAT_TO_ATTR field


def _load_disk_cache():
    if os.path.exists(_LEAGUE_CACHE_FILE):
        with open(_LEAGUE_CACHE_FILE, "r") as f:
            raw = json.load(f)
        return {tuple(map(int, k.split(":"))): v for k, v in raw.items()}
    return {}


def _save_disk_cache(cache):
    serializable = {f"{tid}:{sid}": v for (tid, sid), v in cache.items()}
    with open(_LEAGUE_CACHE_FILE, "w") as f:
        json.dump(serializable, f)


_league_stats_cache = _load_disk_cache()


def _fetch_group_all_pages(nav, tournament_id, season_id, group, page_size=20):
    base_url = (
        f"https://www.sofascore.com/api/v1/unique-tournament/{tournament_id}"
        f"/season/{season_id}/statistics"
    )
    all_entries = []
    offset = 0

    while True:
        params = (
            f"?limit={page_size}&offset={offset}"
            f"&order=-rating&accumulation=total&group={group}"
        )
        data = fetch_json(nav, base_url + params)
        if not data:
            break

        batch = data.get("results", [])
        if not batch:
            break

        all_entries.extend(batch)
        offset += page_size
        time.sleep(0.3)

        if len(batch) < page_size:
            break

    return all_entries


def get_league_stats(nav, tournament_id, season_id):
    """Returns {stat_key: (mean, std)} for the 8 z-scored attributes."""
    cache_key = (tournament_id, season_id)
    if cache_key in _league_stats_cache:
        return _league_stats_cache[cache_key]

    stat_keys = ZSCORE_STAT_TO_ATTR.keys()
    merged = {}  # player_id -> {stat_key: value}

    for group in GROUPS_TO_QUERY:
        entries = _fetch_group_all_pages(nav, tournament_id, season_id, group)
        for entry in entries:
            player_info = entry.get("player", {})
            pid = player_info.get("id")
            if pid is None:
                continue
            merged.setdefault(pid, {})
            for key in stat_keys:
                if key in entry and entry[key] is not None:
                    merged[pid][key] = entry[key]

    values = {key: [] for key in stat_keys}
    for pid, stats in merged.items():
        for key in stat_keys:
            if key in stats:
                values[key].append(stats[key])

    league_stats = {}
    for key, vals in values.items():
        if vals:
            s = pd.Series(vals)
            league_stats[key] = (s.mean(), s.std())
        else:
            league_stats[key] = (None, None)

    _league_stats_cache[cache_key] = league_stats
    _save_disk_cache(_league_stats_cache)
    return league_stats


def zscore(value, mean, std):
    if value is None or mean is None or not std:
        return 0.0
    return (value - mean) / std


# --- Per-player season stats -------------------------------------------------

def get_season_stats(nav, player):

    for season in player.seasons:
        url = (
            f"https://api.sofascore.com/api/v1/player/{player.sofascore_id}"
            f"/unique-tournament/{season['tournament_id']}/season/{season['season_id']}/statistics/overall"
        )

        data = fetch_json(nav, url)['statistics']

        if data is None:
            print("No data available for get_season_stats")
            continue

        league_stats = get_league_stats(nav, season['tournament_id'], season['season_id'])

        # Z-scored attributes
        for sofascore_key, player_attribute in ZSCORE_STAT_TO_ATTR.items():
            if sofascore_key in data.keys():

                mean, std = league_stats.get(sofascore_key, (None, None))
                z = zscore(data.get(sofascore_key), mean, std)

                if sofascore_key == "rating":
                    value = z * data.get("appearances", 1)
                    value += getattr(player, player_attribute)
                    setattr(player, player_attribute, value)
                else:
                    current = getattr(player, player_attribute)
                    setattr(player, player_attribute, current + z)

            else:
                print(player.name, sofascore_key, ": ", "Not found")

        # Raw-sum attributes (no league baseline available for these)
        for sofascore_key, player_attribute in RAW_SUM_STAT_TO_ATTR.items():
            if sofascore_key in data.keys():
                current = getattr(player, player_attribute)
                setattr(player, player_attribute, current + data.get(sofascore_key))
            else:
                print(player.name, sofascore_key, ": ", "Not found")

    return

if __name__ == "__main__":
    nav = webdriver.Firefox()

    players = execute()

    for player in players:
        nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")
        get_season_stats(nav, player)