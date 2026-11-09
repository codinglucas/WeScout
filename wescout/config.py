"""Runtime settings, read from environment variables (and `.env` if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    public_mode: bool
    enable_local_scrapers: bool
    api_football_key: str | None
    api_football_daily_limit: int
    api_football_reserve: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wescout.duckdb"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    if env_file is not None:
        load_dotenv(env_file, override=False)
    return Settings(
        data_dir=Path(os.getenv("WESCOUT_DATA_DIR", "data")),
        # Safe default: public mode on unless explicitly disabled.
        public_mode=_bool(os.getenv("PUBLIC_MODE"), default=True),
        enable_local_scrapers=_bool(os.getenv("ENABLE_LOCAL_SCRAPERS"), default=False),
        api_football_key=os.getenv("API_FOOTBALL_KEY") or None,
        api_football_daily_limit=int(os.getenv("API_FOOTBALL_DAILY_LIMIT", "100")),
        api_football_reserve=int(os.getenv("API_FOOTBALL_RESERVE", "5")),
    )
