from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from app.research.domains.finance.runtime import FinanceRuntime
from app.research.domains.finance.schemas import (
    FinanceOptions,
    MarketSnapshot,
    NewsItem,
    SecFact,
    SecFiling,
    SecurityIdentifier,
)


AS_OF = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
SECURITY = SecurityIdentifier(
    ticker="AAPL",
    exchange="Nasdaq",
    cik=320193,
    company_name="Apple Inc.",
)


class Resolver:
    async def resolve(self, query: str):
        return SECURITY if query.strip().upper() in {"AAPL", "APPLE INC."} else None


class SecConnector:
    async def get_recent_filings(self, security: SecurityIdentifier):
        return [
            SecFiling(
                form="10-K",
                accession_number="0000320193-25-000079",
                filed_at=date(2025, 10, 31),
                report_date=date(2025, 9, 27),
                primary_document="aapl-20250927.htm",
                filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
            )
        ]

    async def get_company_facts(self, security: SecurityIdentifier, *, concepts=None):
        return [
            SecFact(
                taxonomy="us-gaap",
                concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                label="Revenue",
                description="Revenue from customers.",
                unit="USD",
                value=Decimal("391035000000"),
                period_start=date(2024, 9, 29),
                period_end=date(2025, 9, 27),
                filed_at=date(2025, 10, 31),
                form="10-K",
                accession_number="0000320193-25-000079",
                fiscal_year=2025,
                fiscal_period="FY",
            )
        ]


class MarketConnector:
    async def get_snapshot(self, security: SecurityIdentifier, *, retrieved_at: datetime):
        return MarketSnapshot(
            security=security,
            price=Decimal("201.25"),
            previous_close=Decimal("199.50"),
            currency="USD",
            observed_at=datetime(2026, 6, 27, 20, 0, tzinfo=timezone.utc),
            retrieved_at=retrieved_at,
            source_url="https://www.google.com/finance/quote/AAPL:NASDAQ",
        )


class NewsConnector:
    async def search(self, query: str, *, retrieved_at: datetime):
        return [
            NewsItem(
                title="Apple announces a product update",
                url="https://example.com/apple-update",
                source_name="Example News",
                snippet="A factual summary.",
                published_at=datetime(2026, 6, 27, 15, 30, tzinfo=timezone.utc),
                retrieved_at=retrieved_at,
            )
        ]


def test_finance_runtime_completes_named_security_fixture_pipeline() -> None:
    runtime = FinanceRuntime(
        security_resolver=Resolver(),
        sec_connector=SecConnector(),
        market_connector=MarketConnector(),
        news_connector=NewsConnector(),
    )

    result = asyncio.run(
        runtime.research("AAPL", options=FinanceOptions(as_of=AS_OF))
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].security.ticker == "AAPL"
    assert result.candidates[0].supporting_evidence_ids
    assert {item.evidence_type for item in result.evidence} == {
        "filing",
        "fundamental",
        "market",
        "news",
    }
    assert all(item.retrieved_at == AS_OF for item in result.evidence)
    assert result.warnings == ["stage_c_fixture_pipeline_not_an_investment_recommendation"]
