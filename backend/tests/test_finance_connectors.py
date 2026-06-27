from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.research.domains.finance.connectors.google_finance import GoogleFinanceConnector
from app.research.domains.finance.connectors.google_news import GoogleNewsConnector
from app.research.domains.finance.connectors.sec import (
    SecEdgarConnector,
    SecSecurityDirectoryConnector,
)
from app.research.domains.finance.schemas import SecurityIdentifier


AS_OF = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
SEC_USER_AGENT = "PZDeepResearch/0.1 research@example.com"


def aapl() -> SecurityIdentifier:
    return SecurityIdentifier(
        ticker="AAPL",
        exchange="Nasdaq",
        cik=320193,
        company_name="Apple Inc.",
    )


def test_sec_directory_connector_maps_official_fields_and_filters_supported_exchanges() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == SEC_USER_AGENT
        return httpx.Response(
            200,
            json={
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [
                    [320193, "Apple Inc.", "AAPL", "Nasdaq"],
                    [1067983, "Berkshire Hathaway Inc.", "BRK-B", "NYSE"],
                    [999, "OTC Example", "OTCX", "OTC"],
                ],
            },
        )

    connector = SecSecurityDirectoryConnector(
        user_agent=SEC_USER_AGENT,
        transport=httpx.MockTransport(handler),
    )

    securities = asyncio.run(connector.fetch_securities())

    assert [item.ticker for item in securities] == ["AAPL", "BRK-B"]
    assert securities[0].cik == "0000320193"


def test_sec_edgar_connector_normalizes_submissions_and_company_facts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == SEC_USER_AGENT
        if request.url.path.startswith("/submissions/"):
            return httpx.Response(
                200,
                json={
                    "name": "Apple Inc.",
                    "filings": {
                        "recent": {
                            "accessionNumber": ["0000320193-25-000079", "0000320193-25-000001"],
                            "filingDate": ["2025-10-31", "2025-01-01"],
                            "reportDate": ["2025-09-27", "2024-12-31"],
                            "form": ["10-K", "4"],
                            "primaryDocument": ["aapl-20250927.htm", "ownership.xml"],
                        }
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "entityName": "Apple Inc.",
                "facts": {
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "label": "Revenue",
                            "description": "Revenue from customers.",
                            "units": {
                                "USD": [
                                    {
                                        "start": "2024-09-29",
                                        "end": "2025-09-27",
                                        "val": 391035000000,
                                        "accn": "0000320193-25-000079",
                                        "fy": 2025,
                                        "fp": "FY",
                                        "form": "10-K",
                                        "filed": "2025-10-31",
                                    }
                                ]
                            },
                        }
                    }
                },
            },
        )

    connector = SecEdgarConnector(
        user_agent=SEC_USER_AGENT,
        transport=httpx.MockTransport(handler),
    )

    async def scenario():
        filings = await connector.get_recent_filings(aapl())
        facts = await connector.get_company_facts(
            aapl(),
            concepts={"RevenueFromContractWithCustomerExcludingAssessedTax"},
        )
        return filings, facts

    filings, facts = asyncio.run(scenario())

    assert len(filings) == 1
    assert filings[0].form == "10-K"
    assert filings[0].filing_url.endswith("/000032019325000079/aapl-20250927.htm")
    assert facts[0].concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert facts[0].value == Decimal("391035000000")
    assert "units" not in facts[0].model_dump()


def test_google_finance_connector_returns_normalized_market_snapshot_without_raw_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["engine"] == "google_finance"
        assert request.url.params["q"] == "AAPL:NASDAQ"
        return httpx.Response(
            200,
            json={
                "summary": {
                    "title": "Apple Inc",
                    "stock": "AAPL",
                    "exchange": "NASDAQ",
                    "extracted_price": 201.25,
                    "currency": "USD",
                    "date": "Jun 27 2026, 04:00:00 PM UTC-04:00",
                },
                "knowledge_graph": {
                    "key_stats": {
                        "stats": [{"label": "Previous close", "value": "$199.50"}]
                    }
                },
                "search_metadata": {"id": "provider-internal-id"},
            },
        )

    connector = GoogleFinanceConnector(
        api_key="serpapi-key",
        transport=httpx.MockTransport(handler),
    )

    snapshot = asyncio.run(connector.get_snapshot(aapl(), retrieved_at=AS_OF))
    payload = snapshot.model_dump(mode="json")

    assert snapshot.price == Decimal("201.25")
    assert snapshot.previous_close == Decimal("199.50")
    assert snapshot.observed_at.utcoffset().total_seconds() == -4 * 3600
    assert "search_metadata" not in payload
    assert "raw" not in payload


def test_google_news_connector_normalizes_iso_dates_and_source_names() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["engine"] == "google_news"
        assert request.url.params["gl"] == "us"
        return httpx.Response(
            200,
            json={
                "news_results": [
                    {
                        "title": "Apple announces a product update",
                        "link": "https://example.com/apple-update",
                        "source": {"name": "Example News"},
                        "snippet": "A factual summary.",
                        "iso_date": "2026-06-27T15:30:00Z",
                    }
                ],
                "search_metadata": {"id": "do-not-leak"},
            },
        )

    connector = GoogleNewsConnector(
        api_key="serpapi-key",
        transport=httpx.MockTransport(handler),
    )

    items = asyncio.run(connector.search("Apple AAPL", retrieved_at=AS_OF))
    payload = items[0].model_dump(mode="json")

    assert items[0].source_name == "Example News"
    assert payload["published_at"] == "2026-06-27T15:30:00Z"
    assert "search_metadata" not in payload
    assert "raw" not in payload
