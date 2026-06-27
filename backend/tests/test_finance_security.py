from __future__ import annotations

import asyncio

import pytest

from app.research.domains.finance.schemas import SecurityIdentifier
from app.research.domains.finance.security import (
    AmbiguousSecurityError,
    CachedSecurityResolver,
)


class DirectoryProvider:
    def __init__(self, securities: list[SecurityIdentifier]) -> None:
        self.securities = securities
        self.calls = 0

    async def fetch_securities(self) -> list[SecurityIdentifier]:
        self.calls += 1
        return list(self.securities)


def security(ticker: str, name: str, cik: int, exchange: str = "Nasdaq") -> SecurityIdentifier:
    return SecurityIdentifier(
        ticker=ticker,
        company_name=name,
        cik=cik,
        exchange=exchange,
    )


def test_security_resolver_resolves_ticker_and_company_name_from_one_cached_directory() -> None:
    now = [100.0]
    provider = DirectoryProvider(
        [
            security("AAPL", "Apple Inc.", 320193),
            security("MSFT", "Microsoft Corp", 789019),
        ]
    )
    resolver = CachedSecurityResolver(
        provider,
        cache_ttl_seconds=60,
        clock=lambda: now[0],
    )

    async def scenario():
        by_ticker = await resolver.resolve("aapl")
        by_name = await resolver.resolve("Microsoft Corp")
        now[0] = 161.0
        after_expiry = await resolver.resolve("MSFT")
        return by_ticker, by_name, after_expiry

    by_ticker, by_name, after_expiry = asyncio.run(scenario())

    assert by_ticker is not None and by_ticker.cik == "0000320193"
    assert by_name is not None and by_name.ticker == "MSFT"
    assert after_expiry is not None
    assert provider.calls == 2


def test_security_resolver_normalizes_dot_and_dash_share_classes() -> None:
    provider = DirectoryProvider(
        [security("BRK-B", "Berkshire Hathaway Inc.", 1067983, "NYSE")]
    )
    resolver = CachedSecurityResolver(provider)

    resolved = asyncio.run(resolver.resolve("brk.b"))

    assert resolved is not None
    assert resolved.ticker == "BRK-B"


def test_security_resolver_rejects_ambiguous_exact_company_name() -> None:
    provider = DirectoryProvider(
        [
            security("AAA", "Example Holdings", 1, "NYSE"),
            security("BBB", "Example Holdings", 2, "Nasdaq"),
        ]
    )
    resolver = CachedSecurityResolver(provider)

    with pytest.raises(AmbiguousSecurityError):
        asyncio.run(resolver.resolve("Example Holdings"))
