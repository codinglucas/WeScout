"""Builds providers by name and enforces the local-scraper rules.

Licensed providers live in this package. Scraper providers live in the git-ignored
`local_providers/` folder (never pushed). They are only importable when
ENABLE_LOCAL_SCRAPERS=true, and they must declare license="local_scrape".
"""

from __future__ import annotations

import importlib
from typing import Any

from wescout.config import Settings
from wescout.providers.base import ProviderError

LICENSED = ("api_football",)


class LocalScrapersDisabled(ProviderError):
    pass


def create_provider(name: str, settings: Settings, **kwargs: Any) -> Any:
    if name == "api_football":
        from wescout.providers.api_football import ApiFootballProvider

        if not settings.api_football_key:
            raise ProviderError("API_FOOTBALL_KEY is not set (see .env.example)")
        return ApiFootballProvider(settings.api_football_key, cache_dir=settings.raw_dir, **kwargs)

    if not settings.enable_local_scrapers:
        raise LocalScrapersDisabled(
            f"'{name}' is not a licensed provider. Local scrapers are disabled; set "
            "ENABLE_LOCAL_SCRAPERS=true for local personal use only."
        )
    try:
        module = importlib.import_module(f"local_providers.{name}")
    except ModuleNotFoundError as exc:
        raise ProviderError(f"unknown provider '{name}' (not in local_providers/)") from exc
    provider = module.create_provider(settings, **kwargs)
    if getattr(provider, "license", None) != "local_scrape":
        raise ProviderError(f"local provider '{name}' must declare license='local_scrape'")
    return provider
