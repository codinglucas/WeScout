"""
inspect_stat_groups.py

Step 1: fetch statistics/info, which should list the valid `group` values
(summary, attacking, defending, passing, etc.) and the fields each one
returns. This tells us which group(s) to query to get keyPasses,
minutesPlayed, interceptions, dribbledPast, bigChancesCreated,
accuratePasses, totalPasses, appearances — none of which showed up under
group=summary.

Step 2: once we see the group names, try each one (limit=1, just to see
the field set cheaply) against the real statistics endpoint and print
what fields come back.
"""

import json
from selenium import webdriver
from sofascore import fetch_json

TOURNAMENT_ID = 17
SEASON_ID = 76986


def fetch_and_dump(nav, url, filename):
    print(f"\n--- Fetching: {url} ---")
    data = fetch_json(nav, url)
    print(f"[debug] response type: {type(data)}")
    if data is None:
        print("[debug] got None back")
        return None
    if isinstance(data, dict):
        print(f"[debug] top-level keys: {list(data.keys())}")
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[debug] saved to {filename}")
    return data


if __name__ == "__main__":
    nav = webdriver.Firefox()
    nav.get("https://www.sofascore.com")

    # Step 1: discover valid groups
    info_url = (
        f"https://www.sofascore.com/api/v1/unique-tournament/{TOURNAMENT_ID}"
        f"/season/{SEASON_ID}/statistics/info"
    )
    info = fetch_and_dump(nav, info_url, "raw_statistics_info.json")

    # Print it fully since this one's small and we specifically need to read it
    print("\n[debug] full statistics/info content:")
    print(json.dumps(info, indent=2))

    # Step 2: try a handful of likely group names cheaply (limit=1) to see
    # which fields each returns. Adjust this list once step 1's output
    # shows the actual valid group identifiers.
    candidate_groups = ["summary", "attacking", "defending", "passing", "goalkeeper"]

    for group in candidate_groups:
        url = (
            f"https://www.sofascore.com/api/v1/unique-tournament/{TOURNAMENT_ID}"
            f"/season/{SEASON_ID}/statistics"
            f"?limit=1&offset=0&order=-rating&accumulation=total&group={group}"
        )
        data = fetch_and_dump(nav, url, f"raw_group_{group}.json")
        if data and data.get("results"):
            fields = list(data["results"][0].keys())
            print(f"[debug] group='{group}' fields: {fields}")

    nav.quit()d