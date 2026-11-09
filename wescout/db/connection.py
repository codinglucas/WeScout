"""DuckDB connection + a minimal forward-only migration runner."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb

MIGRATIONS_PACKAGE = "wescout.db.migrations"


def _migration_files() -> list[tuple[str, str]]:
    files = resources.files(MIGRATIONS_PACKAGE)
    out = [
        (f.name, f.read_text(encoding="utf-8")) for f in files.iterdir() if f.name.endswith(".sql")
    ]
    return sorted(out)


def migrate(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Apply pending migrations in filename order. Returns the names applied."""
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT current_timestamp)"
    )
    done = {r[0] for r in con.execute("SELECT name FROM schema_migrations").fetchall()}
    applied: list[str] = []
    for name, sql in _migration_files():
        if name in done:
            continue
        con.execute("BEGIN")
        try:
            con.execute(sql)
            con.execute("INSERT INTO schema_migrations (name) VALUES (?)", [name])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        applied.append(name)
    return applied


def connect(path: str | Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the database and bring the schema up to date (unless read-only)."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        migrate(con)
    return con
