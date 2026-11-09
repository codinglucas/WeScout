"""FastAPI app. Reads only from DuckDB - never calls a provider or scraper.

    uv run uvicorn wescout.api.main:app --port 5000

Routes and response shape match the legacy Flask API used by the frontend
(frontend/api-service.js). New fields are additive.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import duckdb
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from wescout.api.players import catalogue, player_detail
from wescout.api.search import SORTS, SearchParams, attributions, search_players
from wescout.config import Settings, load_settings
from wescout.db.connection import connect

POSITIONS = [
    {"id": 1, "code": "gk", "name": "Goalkeeper"},
    {"id": 2, "code": "sweeper", "name": "Sweeper"},
    {"id": 3, "code": "cb", "name": "Center Back"},
    {"id": 4, "code": "lb", "name": "Left Back"},
    {"id": 5, "code": "rb", "name": "Right Back"},
    {"id": 6, "code": "cdm", "name": "Defensive Midfielder"},
    {"id": 7, "code": "cm", "name": "Central Midfielder"},
    {"id": 8, "code": "rm", "name": "Right Midfielder"},
    {"id": 9, "code": "lm", "name": "Left Midfielder"},
    {"id": 10, "code": "cam", "name": "Attacking Midfielder"},
    {"id": 11, "code": "lw", "name": "Left Wing"},
    {"id": 12, "code": "rw", "name": "Right Wing"},
    {"id": 13, "code": "st", "name": "Striker"},
    {"id": 14, "code": "cf", "name": "Center Forward"},
]
POSITION_CODES = {p["code"] for p in POSITIONS}
ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"  # React app (npm run build in web/)
LEGACY_FRONTEND = ROOT / "frontend"


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "error": message}, status_code=status)


def create_app(
    settings: Settings | None = None, con: duckdb.DuckDBPyConnection | None = None
) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if con is not None:
            app.state.con = con
        elif settings.db_path.exists():
            app.state.con = duckdb.connect(str(settings.db_path), read_only=True)
        else:  # empty DB so the API still starts before the first ETL run
            app.state.con = connect(":memory:")
        yield
        if con is None:
            app.state.con.close()

    app = FastAPI(title="WeScout API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    @app.get("/api/players/search")
    def search(
        request: Request,
        min_age: Annotated[int | None, Query(ge=0, le=60)] = None,
        max_age: Annotated[int | None, Query(ge=0, le=60)] = None,
        min_value: Annotated[int | None, Query(ge=0)] = None,
        max_value: Annotated[int | None, Query(ge=0)] = None,
        position: str = "",
        positions: str = "",
        competition: Annotated[int | None, Query(ge=1)] = None,
        sort: str = "rating",
        season: Annotated[int | None, Query(ge=1990, le=2100)] = None,
        min_minutes: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> Any:
        if min_age is not None and max_age is not None and min_age > max_age:
            return _error("min_age cannot be greater than max_age")
        if min_value is not None and max_value is not None and min_value > max_value:
            return _error("min_value cannot be greater than max_value")
        codes = [c.strip().lower() for c in [position, *positions.split(",")] if c.strip()]
        unknown = [c for c in codes if c not in POSITION_CODES]
        if unknown:
            return _error(f"unknown position '{unknown[0]}'")
        if sort not in SORTS:
            return _error(f"sort must be one of: {', '.join(SORTS)}")
        params = SearchParams(
            min_age=min_age, max_age=max_age, min_value=min_value, max_value=max_value,
            positions=tuple(codes), competition_id=competition, season=season,
            min_minutes=min_minutes, sort=sort, limit=limit,
        )  # fmt: skip
        db = request.app.state.con.cursor()
        try:
            players, used_season = search_players(db, params, public=settings.public_mode)
            sources = attributions(db, settings.public_mode)
        finally:
            db.close()
        return {
            "success": True,
            "count": len(players),
            "players": players,
            "season": used_season,
            "public_mode": settings.public_mode,
            "attribution": sources,
        }

    @app.get("/api/players/{player_id}")
    def player(request: Request, player_id: int) -> Any:
        detail = player_detail(request.app.state.con, player_id, public=settings.public_mode)
        if detail is None:
            return _error("player not found", 404)
        return {"success": True, "player": detail}

    @app.get("/api/meta")
    def meta(request: Request) -> dict[str, Any]:
        con = request.app.state.con
        return {
            "success": True,
            "public_mode": settings.public_mode,
            "positions": POSITIONS,
            "sorts": list(SORTS),
            "attribution": attributions(con, settings.public_mode),
            **catalogue(con, public=settings.public_mode),
        }

    @app.get("/api/positions")
    def positions() -> dict[str, Any]:
        return {"success": True, "positions": POSITIONS}

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"success": True, "message": "API is running", "public_mode": settings.public_mode}

    if WEB_DIST.exists():  # React single-page app; client-side routes fall back to index.html
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Any:
            if path.startswith("api/"):
                return _error("not found", 404)
            file = (WEB_DIST / path).resolve()
            if path and file.is_file() and WEB_DIST.resolve() in file.parents:
                return FileResponse(file)
            return FileResponse(WEB_DIST / "index.html")

    elif LEGACY_FRONTEND.exists():  # old static pages until web/ is built
        app.mount("/", StaticFiles(directory=LEGACY_FRONTEND, html=True), name="frontend")

    return app


app = create_app()
