# Design decisions

Short ADR-style log: what was chosen, what was rejected, and why. Newest decisions are added
at the end; superseded ones are marked, not deleted.

---

## ADR-001 — DuckDB as the local database (Phase 1)

**Chosen:** DuckDB, one file (`data/wescout.duckdb`), schema in numbered SQL migrations
(`wescout/db/migrations/`) applied by a small runner that records them in `schema_migrations`.

**Rejected:** PostgreSQL, SQLite.

**Why:**
- The workload is analytical: scans and aggregations over player-season rows (search today;
  per-90 numbers, percentiles and model features in Phase 2). DuckDB is a columnar engine built
  for that, and has `arg_max`, `QUALIFY`, `FILTER` and window functions.
- It's embedded: no server to run in CI or in the demo. The demo is read-only and precomputed,
  so a single file shipped with the app is enough.
- Postgres would be the right call with many concurrent writers or a multi-user product. We
  have one writer (the ETL) and read-only readers.
- SQLite is also embedded, but it's row-oriented and weaker for the Phase 2 feature queries.

**Trade-offs we accepted:**
- **No foreign keys.** DuckDB can't run an upsert (`ON CONFLICT DO UPDATE`) on a row that a
  foreign key points to; it fails with a constraint error. We dropped the `REFERENCES` clauses
  and run `wescout/db/integrity.py` after every ETL load instead. It's tested.
- **One writer at a time.** The API opens the file read-only, so it can't open the file while an
  ETL run holds the write lock. Fine for a precomputed demo; scheduled ETL runs must not overlap
  with serving from the same file (copy the file or load a snapshot).

## ADR-002 — FastAPI replaces Flask

**Chosen:** FastAPI + uvicorn, with the same routes and JSON shape as before
(`/api/players/search`, `/api/positions`, `/api/health`), so the existing frontend works unchanged.

**Rejected:** keeping Flask.

**Why:** query-parameter validation and OpenAPI docs come for free (`/docs`), type hints are the
contract, and `TestClient` makes the API easy to test in-process. The legacy Flask endpoint
couldn't return a result anyway (undefined names, see `docs/benchmarks.md`), so it was a rewrite
either way.

## ADR-003 — Provider abstraction and the "provider IDs everywhere" rule

**Chosen:**
- Every source implements one `Provider` protocol (`wescout/providers/base.py`): `name`,
  `license`, `attribution`, `search_players`, `get_player`, `get_season_stats`,
  `get_market_values`.
- Providers only translate payloads into typed records (`wescout/models.py`). They never touch
  the DB.
- One shared `HttpClient` handles the things every provider needs:
  - sequential requests with a minimum gap;
  - a disk cache of raw responses;
  - daily quota with a reserve;
  - backoff on 429/5xx;
  - a hard stop on 403/challenge responses (`ProviderBlocked`, never retried).
- **Fact tables are keyed by the provider's own IDs** (`source`, `source_player_id`, ...).
  Canonical identity is a single nullable column, `source_players.player_id`.

**Rejected:** one canonical `players` table that every source writes attributes into, with
facts keyed by internal `player_id`.

**Why:**
- Re-matching (a manual fix, a better matcher) only updates `source_players.player_id`. No fact
  rows have to be re-keyed, and a wrong match can never permanently mix up data.
- Player attributes are resolved per query from the allowed sources (ADR-004). A public
  response therefore can't pick up a field that only a scraper provided.
- Two providers can describe the same player-season side by side. The API picks one by priority
  instead of double-counting.

## ADR-004 — Licensing: licensed data in public, scrapers local-only

**Chosen:**
- `sources` table: each source has a `license` of `licensed` or `local_scrape`.
- `PUBLIC_MODE=true` (the default) filters on `license <> 'local_scrape'` in SQL, joined into
  *every* data table the search reads (stats, attributes, positions, market values,
  attribution).
- Scraper code (Transfermarkt, SofaScore) lives in a git-ignored `local_providers/` folder and
  is never pushed. The registry only loads it when `ENABLE_LOCAL_SCRAPERS=true`, and refuses a
  local provider that doesn't declare `license="local_scrape"`.
- Scrapers use an honest User-Agent, ≥ 2–3 s between requests, no parallelism, and a cache.

**Rejected:** keeping scrapers in the public repo behind a flag; filtering scraped data in
Python after the query.

**Why:**
- Transfermarkt, SofaScore and FotMob terms prohibit scraping, and Transfermarkt's also
  prohibit ML/AI training on its content.
- Filtering in SQL on every joined table is the only way to be sure a field doesn't leak.
  `tests/test_api.py` seeds a scraped market value, a scraped detailed position and a
  scraped-only player, and checks that none of them appear in public mode.

**Observed 2026-11-09:** both sites refuse honest non-browser clients (Transfermarkt: HTTP 202
challenge; SofaScore: HTTP 403). We stop on those responses and don't work around them.

## ADR-005 — Matching strategy

**Chosen:**
- API-Football is the anchor: each of its players gets one canonical ID.
- Other sources are matched by fuzzy name (`rapidfuzz` token-set ratio over name variants)
  after transliteration (`anyascii`). Date of birth is a hard gate: a known mismatch rejects the
  pair, a day/month swap scores 0.9, and a missing DOB caps the score below the auto threshold.
  Shared club in the same season adds a small bonus.
- Score ≥ 0.90 links automatically. 0.70–0.90, or two candidates within 0.03 of each other,
  goes to `match_reviews`. Anything lower becomes a new player.
- Manual overrides go in `data/manual_matches.csv` and point at another provider's ID, which
  stays stable across DB rebuilds, never at an internal ID.

**Rejected:** exact name match (fails on "M. Akanji" vs "Manuel Akanji", "Ødegaard" vs
"Odegaard"); name + club only (fails on namesakes like the two "Danilo"s born 1991 and 2001);
`unidecode` (GPL licensed; `anyascii` is ISC).

**Why:** a wrong automatic link is worse than a missing one, because it silently merges two
players' histories, which would poison the value model. So we tune for precision, and send
uncertain cases to a person.

**Evaluation:** `scripts/eval_matching.py` on `eval/match_labels.csv`. Results are in
`docs/benchmarks.md`.

## ADR-006 — API-Football free plan shapes the ETL

**Observed 2026-11-09 with the project key:**
- 100 requests/day and 10/minute.
- Seasons **2022–2024 only**.
- `page` capped at **3** (20 players per page).
- Errors come back as HTTP 200 with an `errors` object.
- No market values.
- Transfer fees are free text in `type`.

**Chosen:**
- Load per club: `/teams?league&season`, then `/players?team&season` (≤ 3 pages per squad),
  keeping only that league's stat rows. About 50 requests per league-season.
- Every unit of work (league-season metadata, club list, one squad page, one club's
  transfers) is a checkpoint. Raw responses are cached on disk. A run that hits the quota ends
  as `partial`, and re-running the same command resumes where it stopped.
- Error bodies are never cached. A `rateLimit` error waits 61 s and retries; a daily-limit
  error stops the run.
- Transfers are fetched per club (`/transfers?team=`), not per player.
- `passes.accuracy` at season level is ambiguous. For Akanji 2023/24 it is 74, while his
  passes per game were 2296 / 34 ≈ 67.5, so it is neither a plausible completion % for a
  Manchester City centre-back nor a per-game count. It's kept verbatim in `extra`, not
  mapped to `accurate_passes`.

**Rejected:** paging `/players?league&season` (blocked after 60 players); per-player requests
(about 500 per league).

**Open problem for Phase 2 (needs a decision):** the value model's target (market-value change)
has **no licensed source** today. API-Football has no market values, StatsBomb open data has none,
and Transfermarkt prohibits ML training. Options:
1. Predict transfer fees from `transfers` (sparse, mixed currencies).
2. Predict performance growth (minutes, rating) instead.
3. Find a licensed market-value source.

The schema supports any of these (`market_values`, `transfers`, and `valued_at` separate from
`fetched_at`).

## ADR-007 — Point-in-time design for Phase 2

- `seasons` stores `start_date`, `end_date` and `is_complete` (from `/leagues`).
- `market_values.valued_at`, `transfers.transfer_date` and `contracts.observed_at` are separate
  from `fetched_at`.
- Age is computed from date of birth at query time. We never store API-Football's `age` field,
  which is the player's age *today* and would leak future information into a historical feature.
- Raw counts only. Per-90 numbers, percentiles and role scores are computed, not stored, so
  they can always be rebuilt "as of" a date.

## ADR-008 — Tooling

- `uv` with a committed `uv.lock` for pinned, reproducible installs. CI runs
  `uv sync --locked`.
- Ruff (lint + format), mypy `--strict` on `wescout/`, and pytest with a socket guard that fails
  any test that tries to use the network.
- Tests use trimmed recorded API-Football fixtures (`tests/fixtures/`). Scraper fixtures are
  hand-written, because the sites refuse to answer, and live in the git-ignored
  `local_providers/tests/`.
