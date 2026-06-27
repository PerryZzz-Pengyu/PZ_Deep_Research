from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.research.domains.finance.connectors.base import FinanceConnectorDataError
from app.research.domains.finance.schemas import (
    SecFact,
    SecFiling,
    SecurityIdentifier,
)


SUPPORTED_EXCHANGES = {"Nasdaq", "NYSE", "NYSE American"}
DEFAULT_FILING_FORMS = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class _SecHttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("SEC requests require an identifying User-Agent")
        self.user_agent = user_agent.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def get_json(self, url: str) -> dict[str, Any]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise FinanceConnectorDataError("SEC response must be a JSON object")
        return payload


class SecSecurityDirectoryConnector:
    def __init__(
        self,
        *,
        user_agent: str,
        endpoint: str = "https://www.sec.gov/files/company_tickers_exchange.json",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.http = _SecHttpClient(
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    async def fetch_securities(self) -> list[SecurityIdentifier]:
        payload = await self.http.get_json(self.endpoint)
        fields = payload.get("fields")
        data = payload.get("data")
        if not isinstance(fields, list) or not isinstance(data, list):
            raise FinanceConnectorDataError("SEC security directory is missing fields/data")
        positions = {str(name): index for index, name in enumerate(fields)}
        required = {"cik", "name", "ticker", "exchange"}
        if not required.issubset(positions):
            raise FinanceConnectorDataError("SEC security directory fields are incomplete")

        securities: list[SecurityIdentifier] = []
        for row in data:
            if not isinstance(row, list) or len(row) < len(fields):
                continue
            exchange = str(row[positions["exchange"]])
            if exchange not in SUPPORTED_EXCHANGES:
                continue
            try:
                securities.append(
                    SecurityIdentifier(
                        cik=row[positions["cik"]],
                        company_name=str(row[positions["name"]]),
                        ticker=str(row[positions["ticker"]]),
                        exchange=exchange,
                    )
                )
            except ValueError:
                continue
        return securities


class SecEdgarConnector:
    def __init__(
        self,
        *,
        user_agent: str,
        data_base_url: str = "https://data.sec.gov",
        archives_base_url: str = "https://www.sec.gov/Archives/edgar/data",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.data_base_url = data_base_url.rstrip("/")
        self.archives_base_url = archives_base_url.rstrip("/")
        self.http = _SecHttpClient(
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    async def get_recent_filings(
        self,
        security: SecurityIdentifier,
        *,
        forms: set[str] | None = None,
    ) -> list[SecFiling]:
        payload = await self.http.get_json(
            f"{self.data_base_url}/submissions/CIK{security.cik}.json"
        )
        recent = payload.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            raise FinanceConnectorDataError("SEC submissions response is missing recent filings")
        accepted_forms = forms or DEFAULT_FILING_FORMS
        accession_numbers = recent.get("accessionNumber", [])
        if not isinstance(accession_numbers, list):
            raise FinanceConnectorDataError("SEC recent filings are not columnar arrays")

        filings: list[SecFiling] = []
        for index, accession in enumerate(accession_numbers):
            form = self._column_value(recent, "form", index)
            filed_at = _parse_date(self._column_value(recent, "filingDate", index))
            primary_document = self._column_value(recent, "primaryDocument", index)
            if form not in accepted_forms or filed_at is None or not primary_document:
                continue
            accession_text = str(accession)
            accession_path = accession_text.replace("-", "")
            filings.append(
                SecFiling(
                    form=form,
                    accession_number=accession_text,
                    filed_at=filed_at,
                    report_date=_parse_date(self._column_value(recent, "reportDate", index)),
                    primary_document=primary_document,
                    filing_url=(
                        f"{self.archives_base_url}/{int(security.cik)}/"
                        f"{accession_path}/{primary_document}"
                    ),
                )
            )
        return filings

    async def get_company_facts(
        self,
        security: SecurityIdentifier,
        *,
        concepts: set[str] | None = None,
    ) -> list[SecFact]:
        payload = await self.http.get_json(
            f"{self.data_base_url}/api/xbrl/companyfacts/CIK{security.cik}.json"
        )
        facts_root = payload.get("facts")
        if not isinstance(facts_root, dict):
            raise FinanceConnectorDataError("SEC company facts response is missing facts")

        normalized: list[SecFact] = []
        for taxonomy, taxonomy_facts in facts_root.items():
            if not isinstance(taxonomy_facts, dict):
                continue
            for concept, concept_data in taxonomy_facts.items():
                if concepts is not None and concept not in concepts:
                    continue
                if not isinstance(concept_data, dict):
                    continue
                label = str(concept_data.get("label") or concept)
                description = str(concept_data.get("description") or "")
                units = concept_data.get("units")
                if not isinstance(units, dict):
                    continue
                for unit, entries in units.items():
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        fact = self._normalize_fact(
                            taxonomy=str(taxonomy),
                            concept=str(concept),
                            label=label,
                            description=description,
                            unit=str(unit),
                            entry=entry,
                        )
                        if fact is not None:
                            normalized.append(fact)
        normalized.sort(key=lambda item: (item.filed_at, item.period_end), reverse=True)
        return normalized

    @staticmethod
    def _column_value(recent: dict[str, Any], name: str, index: int) -> str:
        values = recent.get(name)
        if not isinstance(values, list) or index >= len(values):
            return ""
        value = values[index]
        return str(value) if value is not None else ""

    @staticmethod
    def _normalize_fact(
        *,
        taxonomy: str,
        concept: str,
        label: str,
        description: str,
        unit: str,
        entry: object,
    ) -> SecFact | None:
        if not isinstance(entry, dict):
            return None
        period_end = _parse_date(entry.get("end"))
        filed_at = _parse_date(entry.get("filed"))
        form = str(entry.get("form") or "")
        accession = str(entry.get("accn") or "")
        if period_end is None or filed_at is None or not form or not accession:
            return None
        try:
            value = Decimal(str(entry.get("val")))
        except (InvalidOperation, TypeError, ValueError):
            return None
        fiscal_year = entry.get("fy")
        return SecFact(
            taxonomy=taxonomy,
            concept=concept,
            label=label,
            description=description,
            unit=unit,
            value=value,
            period_start=_parse_date(entry.get("start")),
            period_end=period_end,
            filed_at=filed_at,
            form=form,
            accession_number=accession,
            fiscal_year=fiscal_year if isinstance(fiscal_year, int) else None,
            fiscal_period=str(entry.get("fp")) if entry.get("fp") else None,
        )
