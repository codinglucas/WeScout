# WeScout

> **Disclaimer:** This project is a personal, educational exercise built for learning purposes (web scraping, APIs, data handling, and basic frontend/backend integration). It is **not** a commercial product, and there is **no intent to commercialize, sell, or monetize** it in any way. It scrapes publicly viewable data from Transfermarkt and SofaScore for personal, non-commercial use only, and is not affiliated with, endorsed by, or sponsored by either site. Use of this code is subject to those sites' respective terms of service.

WeScout is a football (soccer) scouting tool that combines player data scraped from **Transfermarkt** (market value, club, basic bio) with detailed performance statistics pulled from **SofaScore** (ratings, goals, assists, tackles, passing, etc.), and exposes it through a Flask API and a simple web dashboard.

## How it works

1. **Player discovery (`transfermarkt_scrapper.py`)** — Submits a filtered search (age range, market value, position) to Transfermarkt's advanced player search and parses the results table with BeautifulSoup into a list of `Player` objects. A curated fallback list is also available via `manual_player_list.py` for testing without hitting Transfermarkt.
2. **Stat enrichment (`sofascore.py`)** — Uses Selenium to drive a browser against SofaScore:
   - Matches each Transfermarkt player to their SofaScore player ID (`match_id`).
   - Pulls the player's recent seasons (current year + prior two) per competition (`retrieve_year_based_seasons`).
   - Fetches season/competition statistics via SofaScore's internal API using an in-page `fetch` call (`fetch_json`).
   - Caches lookups to disk (`player_cache.json`) to avoid re-scraping the same players.
3. **Data model (`dataclass.py`)** — A `Player` dataclass holds identity fields (name, club, value, SofaScore ID) plus per-season stats (rating, goals, assists, key passes, minutes played, tackles, interceptions, dribbled past, big chances created, accurate/total passes) and a `seasons` list.
4. **API (`app.py`)** — A Flask + Flask-CORS backend exposing:
   - `GET /api/players/search` — filter players by age, market value, and position, returning enriched stats as JSON.
   - `GET /api/positions` — list of supported position codes (GK through CF).
   - `GET /api/health` — basic health check.
5. **Frontend (`index.html`, `dashboard.html`, `login.html`, `lists.html` + matching `.css`/`.js`)** — A static HTML/CSS/JS dashboard that calls the Flask API (`api-service.js`) to search and display players.
6. **Experimental (`ml.py`)** — Early-stage work computing league-average stats (e.g. average goals) per competition, intended as a first step toward a model that projects how a player's output would translate to a different league.

## Tech stack

- **Backend:** Python, Flask, Flask-CORS
- **Scraping:** Selenium (SofaScore), Requests + BeautifulSoup (Transfermarkt)
- **Data:** Python dataclasses, Pandas (DataFrame assembly in the API layer)
- **Frontend:** HTML, CSS, vanilla JavaScript

## Project structure

```
dataclass.py                 # Player dataclass (shared data model)
transfermarkt_scrapper.py    # Transfermarkt search + parsing -> list[Player]
manual_player_list.py        # Hardcoded player list for testing
sofascore.py                 # SofaScore ID matching, season/stat scraping, caching
ml.py                        # Experimental league-average stats / projection work
start.py                     # Early standalone Transfermarkt scraping script
app.py / app_v2.py           # Flask API
index.html, dashboard.html,  # Frontend pages
login.html, lists.html
*.css, *.js                  # Frontend styling and API client
```

## Running locally

1. Install Python dependencies: `flask`, `flask-cors`, `selenium`, `requests`, `beautifulsoup4`, `pandas`.
2. Make sure a Selenium-compatible browser driver (e.g. geckodriver for Firefox) is installed and on your `PATH`.
3. Start the API:
   ```
   python app.py
   ```
4. Open `index.html` (or serve the frontend files with a static server) — it talks to the API at `http://localhost:5000/api` by default (see `api-service.js`).

## Status / notes

This is an active, evolving project. Some files (`start.py`, `test.py`, `app_v2.py`) reflect earlier iterations kept alongside the current versions. `ml.py` is a work-in-progress toward a cross-league player projection model.
