"""ETL: provider -> DuckDB. Idempotent, resumable, quota-aware.

    uv run python -m wescout.etl --provider api_football --competitions 39,140 --seasons 2023
    uv run python -m wescout.etl --resolve-only

Resumability: every unit of work (one league-season, one page, one team's transfers) is a
row in etl_checkpoints; finished units are skipped on the next run. Raw responses are cached
on disk, so re-reading page 1 to learn the page count costs no request. When the daily quota
runs out the run ends as 'partial'; run the same command again tomorrow.

Scheduling: the command is safe to run from cron/GitHub Actions as-is (not set up here).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from wescout.config import Settings, load_settings
from wescout.db import repository as repo
from wescout.db.connection import connect
from wescout.db.integrity import check_integrity
from wescout.models import SearchFilters
from wescout.providers.api_football import ApiFootballProvider
from wescout.providers.base import ProviderBlocked, QuotaExhausted
from wescout.providers.http import QuotaTracker
from wescout.providers.registry import create_provider
from wescout.resolve import resolve_players

log = logging.getLogger("wescout.etl")

# Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Brasileirão
DEFAULT_COMPETITIONS = (39, 140, 135, 78, 61, 88, 94, 71)
DEFAULT_SEASONS = (2023,)
MANUAL_MATCHES = "manual_matches.csv"


@dataclass
class RunSummary:
    run_id: int
    provider: str
    status: str = "running"
    records: int = 0
    requests_used: int = 0
    pages_done: int = 0
    pages_skipped: int = 0
    runtime_s: float = 0.0
    quota_remaining: int | None = None
    message: str = ""


def _today_utc() -> date:
    return datetime.now(UTC).date()


class _Tx:
    """Each unit of work is one transaction: a crash never leaves half a page behind."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con

    def __enter__(self) -> None:
        self.con.execute("BEGIN")

    def __exit__(self, exc_type: object, *_: object) -> None:
        self.con.execute("ROLLBACK" if exc_type else "COMMIT")


def run_api_football(
    con: duckdb.DuckDBPyConnection,
    provider: ApiFootballProvider,
    competitions: list[int],
    seasons: list[int],
    summary: RunSummary,
    *,
    transfers: bool = False,
    max_requests: int | None = None,
) -> None:
    name = provider.name
    today = _today_utc()

    def budget_left() -> bool:
        return max_requests is None or provider.requests_made < max_requests

    for season in seasons:
        for league in competitions:
            tag = f"{league}:{season}"
            # 1) League-season metadata (dates -> point-in-time features later).
            key = f"league:{tag}"
            if not repo.checkpoint_done(con, name, key):
                if not budget_left():
                    raise _BudgetReached
                info = provider.fetch_league_season(league, season)
                with _Tx(con):
                    if info is not None:
                        fetched = repo.utcnow()
                        comp_id = repo.get_or_create_competition(
                            con, name, info["competition"], fetched
                        )
                        repo.get_or_create_season(
                            con, comp_id, season, start_date=info["start"],
                            end_date=info["end"],
                            is_complete=bool(info["end"] and info["end"] < today),
                        )  # fmt: skip
                    repo.mark_checkpoint(con, name, key, "done", 1 if info else 0)

            row = con.execute(
                "SELECT s.is_complete FROM seasons s JOIN external_ids e"
                " ON e.entity_type = 'competition' AND e.entity_id = s.competition_id"
                " WHERE e.source = ? AND e.source_id = ? AND s.start_year = ?",
                [name, str(league), season],
            ).fetchone()
            complete = bool(row[0]) if row else False

            # 2) Player pages.
            page, total = 1, 1
            while page <= total:
                key = f"players:{tag}:{page}"
                done = repo.checkpoint_done(con, name, key)
                if done and page > 1:
                    summary.pages_skipped += 1
                    page += 1
                    continue
                if not done and not budget_left():
                    raise _BudgetReached
                # Page 1 is re-read (from the disk cache when already fetched) for the count.
                result = provider.fetch_players_page(league, season, page)
                total = result.total_pages or 1
                if done:
                    summary.pages_skipped += 1
                else:
                    fetched = repo.utcnow()
                    with _Tx(con):
                        n = repo.upsert_source_players(con, result.players, fetched)
                        n += repo.upsert_season_stats(
                            con, result.stats, fetched, season_complete=complete
                        )
                        repo.mark_checkpoint(con, name, key, "done", n)
                    summary.records += n
                    summary.pages_done += 1
                    log.info("%s page %d/%d: %d records", tag, page, total, n)
                page += 1

            # 3) Transfers per club (one request per club, not per player).
            if transfers:
                club_ids = [
                    r[0]
                    for r in con.execute(
                        "SELECT DISTINCT e.source_id FROM player_season_stats s"
                        " JOIN seasons x USING (season_id)"
                        " JOIN external_ids c ON c.entity_type = 'competition'"
                        "  AND c.entity_id = x.competition_id AND c.source = s.source"
                        " JOIN external_ids e ON e.entity_type = 'club'"
                        "  AND e.entity_id = s.club_id AND e.source = s.source"
                        " WHERE s.source = ? AND c.source_id = ? AND x.start_year = ?"
                        " ORDER BY 1",
                        [name, str(league), season],
                    ).fetchall()
                ]
                for team in club_ids:
                    key = f"transfers:team:{team}"
                    if repo.checkpoint_done(con, name, key):
                        continue
                    if not budget_left():
                        raise _BudgetReached
                    rows = provider.fetch_team_transfers(int(team))
                    with _Tx(con):
                        n = repo.upsert_transfers(con, rows, repo.utcnow())
                        repo.mark_checkpoint(con, name, key, "done", n)
                    summary.records += n


class _BudgetReached(Exception):
    pass


def run_local_scraper(
    con: duckdb.DuckDBPyConnection, provider: Any, filters: SearchFilters, summary: RunSummary
) -> None:
    result = provider.search_players(filters)
    fetched = repo.utcnow()
    with _Tx(con):
        summary.records += repo.upsert_source_players(con, result.players, fetched)
        summary.records += repo.upsert_market_values(con, result.market_values, fetched)
        summary.records += repo.upsert_season_stats(con, result.stats, fetched)


def _quota(con: duckdb.DuckDBPyConnection, settings: Settings) -> QuotaTracker:
    day = _today_utc()
    return QuotaTracker(
        daily_limit=settings.api_football_daily_limit,
        reserve=settings.api_football_reserve,
        used_today=repo.api_usage_on(con, "api_football", day),
        on_request=lambda: repo.add_api_usage(con, "api_football", day),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m wescout.etl",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--provider", default="api_football")
    parser.add_argument("--competitions", default=",".join(map(str, DEFAULT_COMPETITIONS)))
    parser.add_argument("--seasons", "--season", default=",".join(map(str, DEFAULT_SEASONS)))
    parser.add_argument("--transfers", action="store_true", help="also load club transfers")
    parser.add_argument("--max-requests", type=int, default=None, help="stop after N requests")
    parser.add_argument("--resolve-only", action="store_true", help="only run ID matching")
    parser.add_argument("--db", type=Path, default=None)
    # Filters for local scraper providers (search-based).
    parser.add_argument("--position")
    parser.add_argument("--min-age", type=int)
    parser.add_argument("--max-age", type=int)
    parser.add_argument("--max-value", type=int)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    con = connect(args.db or settings.db_path)
    manual = settings.data_dir / MANUAL_MATCHES

    if args.resolve_only:
        stats = resolve_players(con, manual)
        log.info("resolve: %s", asdict(stats))
        return 0

    started = time.perf_counter()
    run_args = {k: v for k, v in vars(args).items() if v is not None and k != "db"}
    summary = RunSummary(repo.start_run(con, args.provider, run_args), args.provider)
    provider: Any = None
    try:
        kwargs: dict[str, Any] = {}
        if args.provider == "api_football":
            kwargs["quota"] = _quota(con, settings)
        provider = create_provider(args.provider, settings, **kwargs)
        repo.register_source(
            con,
            provider.name,
            provider.license,
            provider.attribution,
            getattr(provider, "url", None),
        )
        if args.provider == "api_football":
            seasons = [int(s) for s in args.seasons.split(",")]
            run_api_football(
                con, provider, [int(c) for c in args.competitions.split(",")], seasons, summary,
                transfers=args.transfers, max_requests=args.max_requests,
            )  # fmt: skip
        else:
            filters = SearchFilters(min_age=args.min_age, max_age=args.max_age,
                                    max_value=args.max_value, position=args.position)  # fmt: skip
            run_local_scraper(con, provider, filters, summary)
        summary.status = "ok"
    except (QuotaExhausted, _BudgetReached) as exc:
        summary.status = "partial"
        summary.message = f"stopped: {exc or 'max requests reached'}; re-run to resume"
    except ProviderBlocked as exc:
        summary.status = "failed"
        summary.message = f"provider refused the request ({exc}); not retrying"
    except Exception as exc:
        summary.status = "failed"
        summary.message = repr(exc)
        log.exception("ETL failed")
    finally:
        if provider is not None:
            summary.requests_used = provider.requests_made
            quota = getattr(getattr(provider, "client", None), "quota", None)
            summary.quota_remaining = quota.remaining if quota else None
        resolve = resolve_players(con, manual)
        problems = check_integrity(con)
        if problems:
            summary.message += f" integrity: {problems}"
        summary.runtime_s = round(time.perf_counter() - started, 2)
        repo.finish_run(con, summary.run_id, summary.status, summary.records,
                        summary.requests_used, summary.message)  # fmt: skip
        log.info("resolve: %s", asdict(resolve))
        print(json.dumps(asdict(summary)))
    return 0 if summary.status in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
