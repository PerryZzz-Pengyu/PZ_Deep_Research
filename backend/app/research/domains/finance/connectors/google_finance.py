from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.research.domains.finance.connectors.base import FinanceConnectorDataError
from app.research.domains.finance.schemas import MarketSnapshot, SecurityIdentifier


EXCHANGE_CODES = {
    "Nasdaq": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE American": "NYSEAMERICAN",
}


def _decimal_from_display(value: object) -> Decimal | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_finance_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FinanceConnectorDataError("Google Finance summary is missing its observation time")
    formats = (
        "%b %d %Y, %I:%M:%S %p UTC%z",
        "%b %d, %I:%M:%S %p GMT%z",
    )
    for date_format in formats:
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
    raise FinanceConnectorDataError(f"Unsupported Google Finance date: {value}")


class GoogleFinanceConnector:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = "https://serpapi.com/search",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Google Finance connector requires a SerpApi key")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def get_snapshot(
        self,
        security: SecurityIdentifier,
        *,
        retrieved_at: datetime,
    ) -> MarketSnapshot:
        exchange_code = EXCHANGE_CODES[security.exchange]
        query = f"{security.ticker}:{exchange_code}"
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.get(
                self.endpoint,
                params={
                    "engine": "google_finance",
                    "q": query,
                    "hl": "en",
                    "api_key": self.api_key,
                    "output": "json",
                },
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("error"):
            raise FinanceConnectorDataError(
                str(payload.get("error") if isinstance(payload, dict) else "Invalid response")
            )
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            raise FinanceConnectorDataError("Google Finance response is missing summary")
        try:
            price = Decimal(str(summary["extracted_price"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise FinanceConnectorDataError("Google Finance summary has no numeric price") from exc

        previous_close = None
        stats = (
            payload.get("knowledge_graph", {})
            .get("key_stats", {})
            .get("stats", [])
        )
        if isinstance(stats, list):
            for item in stats:
                if isinstance(item, dict) and str(item.get("label", "")).casefold() == "previous close":
                    previous_close = _decimal_from_display(item.get("value"))
                    break

        return MarketSnapshot(
            security=security,
            price=price,
            previous_close=previous_close,
            currency=str(summary.get("currency") or "USD"),
            observed_at=_parse_finance_datetime(summary.get("date")),
            retrieved_at=retrieved_at,
            source_url=f"https://www.google.com/finance/quote/{query}",
        )
