# Benchmarks

All numbers are recorded with the date, machine and method so they can be reproduced.
Machine: MacBook Air (Apple Silicon), macOS 26, Python 3.14, home broadband.

## 1. Player search latency

### Before: Flask + live scraping (measured/estimated 2026-11-09)

**Status of the legacy endpoint.** `GET /api/players/search` in the legacy `app.py` cannot
return a result: after `execute()` runs it references `player_list`, `get_player_data` and
`dataframe_organizer`, which are undefined, so every request ends in HTTP 500. It also ignores
the filters (it enriches a hardcoded 5-player list) and has the stats call commented out.
So the "before" number below is the cost of the request path the endpoint was designed to run.

**What was measured live** (sequential, ≥ 2 s between requests, honest User-Agent
`WeScout/0.1 (personal research project; …)`, plain `requests`):

| Request | Result | Latency |
|---|---|---|
| Transfermarkt advanced search (LB, age ≤ 23, value ≤ €15M), ×3 different searches | HTTP 202, bot-challenge page, no results table | 0.03–0.22 s |
| SofaScore `/api/v1/search/all` for 3 players | HTTP 403 | ~0.07 s |

Both sites refuse non-browser clients that identify themselves honestly. The legacy code only
worked by sending a spoofed Firefox User-Agent (Transfermarkt) and by driving a real browser
with Selenium (SofaScore). We do not work around those protections, so a live end-to-end run
was not possible. Selenium could not be run either (no Firefox/geckodriver on this machine).

**Estimate from the code path.** One search = 1 Transfermarkt POST (up to 25 rows per page),
then, per player, in a Selenium-driven Firefox:

| Step (legacy `sofascore.py`) | Requests per player |
|---|---|
| ID search, up to 3 query variants (`match_id`) — skipped on cache hit | 1–3 |
| Player page load (`nav.get`), done twice (`execute` + `retrieve_year_based_seasons`) | 2 full page loads |
| Seasons list (`statistics/seasons`) | 1 |
| Season stats per (competition × year) in the last 3 years (`get_season_stats`) | ~3–6 |
| **Total** | **~8–12** |

- Without rate limiting (how the legacy code ran): 25 players × (2 page loads × ~2.5 s +
  ~8 JSON fetches × ~0.3 s) + ~5 s browser start ≈ **~3 minutes per search**.
- With the ≥ 2 s gap this project now requires for scrapers: 25 × ~10 requests × 2 s ≈
  **~8 minutes per search**.
- Requests sent to third-party sites per search: **~200–300**. The cache (`player_cache.json`)
  only saved the ID lookup, not the stats.

These are estimates (stated as such), with per-request latencies taken from typical page loads,
not measured on this machine.

### After: FastAPI + DuckDB

_To be filled in at the end of Phase 1 (`scripts/benchmark_search.py`)._

## 2. API-Football quota (checked 2026-11-09 via `/status` and response headers)

- Free plan: **100 requests/day**, **10 requests/minute** (`x-ratelimit-requests-limit: 100`,
  `x-ratelimit-limit: 10`).
- Seasons: free plan can only access **2022–2024**. Requesting 2025 returns
  `"Free plans do not have access to this season, try from 2022 to 2024."`
- `/players?league=39&season=2023` has **51 pages** of 20 players, so one league-season costs
  ~50 requests. 8 leagues × 3 seasons ≈ 1,200 requests ≈ 12 days of free quota.

## 3. ETL runtime and coverage

_To be filled in by ETL runs._

## 4. ID matching (precision/recall)

Method: `uv run python scripts/eval_matching.py` scores every hand-labelled pair in
`eval/match_labels.csv`. A pair counts as a predicted match when its score reaches the
auto-link threshold (0.90), which is what the pipeline would link without a human. Pairs
scoring 0.70–0.90 go to the review list.

| Date | Labelled pairs | Precision | Recall | False links | Sent to review |
|---|---|---|---|---|---|
| 2026-11-09 | 21 (16 matches, 5 non-matches) | **1.00** | **0.81** | 0 | 4 |

The 3 missed matches all went to review, not to a wrong player:
- 2 pairs where one source has no date of birth (capped below auto-link by design);
- "Rodri" vs "Rodrigo Hernández", a nickname, which needs a manual override.

The starter sample is small and was built to include tricky cases: diacritics,
transliteration, initials, name order, long Portuguese names, day/month swaps, and namesakes
(two Danilos, three Gabriels at Arsenal). The next step is extending it to about 200
randomly sampled pairs, which will give a less optimistic number.
