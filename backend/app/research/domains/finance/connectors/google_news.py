from __future__ import annotations

from datetime import datetime

import httpx

from app.research.domains.finance.connectors.base import FinanceConnectorDataError
from app.research.domains.finance.schemas import NewsItem


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _source_name(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else ""
    return ""


class GoogleNewsConnector:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = "https://serpapi.com/search",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Google News connector requires a SerpApi key")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def search(
        self,
        query: str,
        *,
        retrieved_at: datetime,
    ) -> list[NewsItem]:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.get(
                self.endpoint,
                params={
                    "engine": "google_news",
                    "q": query,
                    "gl": "us",
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
        results = payload.get("news_results", [])
        if not isinstance(results, list):
            raise FinanceConnectorDataError("Google News response has invalid news_results")

        items: list[NewsItem] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            title = str(result.get("title") or "").strip()
            url = str(result.get("link") or "").strip()
            source_name = _source_name(result.get("source")).strip()
            if not title or not url or not source_name:
                continue
            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source_name=source_name,
                    snippet=str(result.get("snippet") or ""),
                    published_at=_parse_iso_datetime(result.get("iso_date")),
                    retrieved_at=retrieved_at,
                )
            )
        return items
