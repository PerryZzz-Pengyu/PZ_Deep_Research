from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from typing import Protocol

from app.research.domains.finance.schemas import SecurityIdentifier


class SecurityDirectoryProvider(Protocol):
    async def fetch_securities(self) -> list[SecurityIdentifier]: ...


class AmbiguousSecurityError(LookupError):
    pass


def normalize_ticker(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def normalize_company_name(value: str) -> str:
    normalized = value.casefold().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


class CachedSecurityResolver:
    """Exact ticker/name resolver with a bounded in-memory directory cache."""

    def __init__(
        self,
        provider: SecurityDirectoryProvider,
        *,
        cache_ttl_seconds: float = 86400,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider = provider
        self.cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self.clock = clock
        self._expires_at = 0.0
        self._securities: list[SecurityIdentifier] = []
        self._lock = asyncio.Lock()

    async def _directory(self) -> list[SecurityIdentifier]:
        now = self.clock()
        if self._securities and now < self._expires_at:
            return self._securities
        async with self._lock:
            now = self.clock()
            if self._securities and now < self._expires_at:
                return self._securities
            self._securities = await self.provider.fetch_securities()
            self._expires_at = now + self.cache_ttl_seconds
            return self._securities

    async def resolve(self, query: str) -> SecurityIdentifier | None:
        raw = query.strip()
        if not raw:
            return None
        securities = await self._directory()
        ticker = normalize_ticker(raw)
        ticker_matches = [item for item in securities if item.ticker == ticker]
        if len(ticker_matches) == 1:
            return ticker_matches[0]
        if len(ticker_matches) > 1:
            raise AmbiguousSecurityError(f"Ticker resolves to multiple securities: {query}")

        company_name = normalize_company_name(raw)
        name_matches = [
            item
            for item in securities
            if normalize_company_name(item.company_name) == company_name
        ]
        if len(name_matches) == 1:
            return name_matches[0]
        if len(name_matches) > 1:
            raise AmbiguousSecurityError(f"Company name is ambiguous: {query}")
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._securities = []
            self._expires_at = 0.0
