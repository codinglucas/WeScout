"""Shared HTTP client for providers: rate limiting, raw-response cache, quota, backoff.

One client per provider. Requests are strictly sequential (no parallelism).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from wescout.providers.base import ProviderBlocked, ProviderError, QuotaExhausted

log = logging.getLogger(__name__)

USER_AGENT = "WeScout/0.2 (personal research project; https://github.com/codinglucas/WeScout)"


def request_key(source: str, endpoint: str, params: dict[str, Any]) -> str:
    payload = json.dumps([source, endpoint, sorted(params.items())], default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class QuotaTracker:
    """Counts requests per UTC day. `on_request` lets the caller persist usage (api_usage table).

    The provider's own header (remaining requests) wins when it is lower than our count,
    e.g. if the key was also used from another machine.
    """

    daily_limit: int
    reserve: int = 0
    used_today: int = 0
    remaining_reported: int | None = None
    on_request: Callable[[], None] | None = None

    @property
    def remaining(self) -> int:
        ours = self.daily_limit - self.used_today
        if self.remaining_reported is not None:
            return min(ours, self.remaining_reported)
        return ours

    def check(self) -> None:
        if self.remaining <= self.reserve:
            raise QuotaExhausted(
                f"daily budget reached: {self.remaining} left, reserve {self.reserve}"
            )

    def record(self) -> None:
        self.used_today += 1
        if self.remaining_reported is not None:
            self.remaining_reported -= 1
        if self.on_request:
            self.on_request()


@dataclass
class HttpClient:
    source: str
    base_url: str
    headers: dict[str, str] = field(default_factory=dict)
    min_interval_s: float = 2.0
    cache_dir: Path | None = None
    quota: QuotaTracker | None = None
    max_retries: int = 3
    transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    on_raw: Callable[[str, str, dict[str, Any], str, int], None] | None = None
    requests_made: int = 0
    _last_request_at: float | None = None
    _client: httpx.Client | None = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={"User-Agent": USER_AGENT, **self.headers},
                timeout=30.0,
                transport=self.transport,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def _cache_path(self, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / self.source / key[:2] / key

    def _wait_turn(self) -> None:
        if self._last_request_at is not None:
            wait = self.min_interval_s - (self.clock() - self._last_request_at)
            if wait > 0:
                self.sleep(wait)
        self._last_request_at = self.clock()

    def get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        use_cache: bool = True,
        is_ok: Callable[[Any], bool] = lambda _: True,
    ) -> Any:
        """GET endpoint and return parsed JSON. Cached responses cost no request.

        `is_ok` decides whether a 200 response is cacheable (APIs that report errors in the
        body, like API-Football, must not have those cached).
        """
        text = self.fetch_text(
            endpoint, params, use_cache=use_cache, is_ok=lambda t: is_ok(json.loads(t))
        )
        return json.loads(text)

    def fetch_text(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        method: str = "GET",
        form: dict[str, Any] | None = None,
        use_cache: bool = True,
        is_ok: Callable[[str], bool] = lambda _: True,
    ) -> str:
        """Fetch a page (GET, or POST with a form) and return the body as text."""
        params = dict(params or {})
        key = request_key(self.source, f"{method} {endpoint}", {**params, "__form": form})
        path = self._cache_path(key)
        if use_cache and path is not None and path.exists():
            return path.read_text(encoding="utf-8")

        attempt = 0
        while True:
            if self.quota is not None:
                self.quota.check()
            self._wait_turn()
            response = self._http().request(method, endpoint, params=params, data=form)
            self.requests_made += 1
            if self.quota is not None:
                self.quota.record()
                header = response.headers.get("x-ratelimit-requests-remaining")
                if header is not None and header.isdigit():
                    self.quota.remaining_reported = int(header)

            # 202 is how some bot-protection layers answer (e.g. a JS challenge page).
            if response.status_code in (202, 401, 403):
                raise ProviderBlocked(f"{self.source} refused {endpoint}: {response.status_code}")
            if response.status_code == 429 or response.status_code >= 500:
                attempt += 1
                if attempt > self.max_retries:
                    raise ProviderError(f"{self.source} {endpoint}: {response.status_code}")
                backoff = self.min_interval_s * (2**attempt)
                log.warning("%s %s -> %s, retry in %.1fs", self.source, endpoint,
                            response.status_code, backoff)  # fmt: skip
                self.sleep(backoff)
                continue
            if response.status_code != 200:
                raise ProviderError(f"{self.source} {endpoint}: HTTP {response.status_code}")

            text = response.text
            if path is not None and is_ok(text):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                if self.on_raw:
                    self.on_raw(key, endpoint, params, str(path), response.status_code)
            return text


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
