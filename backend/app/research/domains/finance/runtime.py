from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from typing import Protocol

from app.research.domains.finance.schemas import (
    CandidateResearch,
    FinanceOptions,
    FinanceResearchResult,
    FinancialEvidence,
    MarketSnapshot,
    NewsItem,
    SecFact,
    SecFiling,
    SecurityIdentifier,
)


class SecurityResolver(Protocol):
    async def resolve(self, query: str) -> SecurityIdentifier | None: ...


class SecConnector(Protocol):
    async def get_recent_filings(
        self,
        security: SecurityIdentifier,
        *,
        forms: set[str] | None = None,
    ) -> list[SecFiling]: ...

    async def get_company_facts(
        self,
        security: SecurityIdentifier,
        *,
        concepts: set[str] | None = None,
    ) -> list[SecFact]: ...


class MarketConnector(Protocol):
    async def get_snapshot(
        self,
        security: SecurityIdentifier,
        *,
        retrieved_at: datetime,
    ) -> MarketSnapshot: ...


class NewsConnector(Protocol):
    async def search(
        self,
        query: str,
        *,
        retrieved_at: datetime,
    ) -> list[NewsItem]: ...


class SecurityNotFoundError(LookupError):
    pass


def _date_as_utc(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


class FinanceRuntime:
    """Stage-C named-security fixture pipeline; not registered in the public API yet."""

    DEFAULT_FACT_CONCEPTS = {
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss",
        "Assets",
        "Liabilities",
        "CashAndCashEquivalentsAtCarryingValue",
        "NetCashProvidedByUsedInOperatingActivities",
    }

    def __init__(
        self,
        *,
        security_resolver: SecurityResolver,
        sec_connector: SecConnector,
        market_connector: MarketConnector,
        news_connector: NewsConnector,
    ) -> None:
        self.security_resolver = security_resolver
        self.sec_connector = sec_connector
        self.market_connector = market_connector
        self.news_connector = news_connector

    async def research(
        self,
        query: str,
        *,
        options: FinanceOptions,
    ) -> FinanceResearchResult:
        security = await self.security_resolver.resolve(query)
        if security is None:
            raise SecurityNotFoundError(f"Unable to resolve a supported US security: {query}")

        filings_task = self.sec_connector.get_recent_filings(security)
        facts_task = self.sec_connector.get_company_facts(
            security,
            concepts=self.DEFAULT_FACT_CONCEPTS,
        )
        market_task = self.market_connector.get_snapshot(
            security,
            retrieved_at=options.as_of,
        )
        news_task = self.news_connector.search(
            f"{security.company_name} {security.ticker}",
            retrieved_at=options.as_of,
        )
        filings, facts, market, news = await asyncio.gather(
            filings_task,
            facts_task,
            market_task,
            news_task,
        )

        evidence = self._build_evidence(
            security,
            filings=filings,
            facts=facts,
            market=market,
            news=news,
            retrieved_at=options.as_of,
        )
        supporting_ids = [item.evidence_id for item in evidence]
        candidate = CandidateResearch(
            security=security,
            selection_reason=(
                "Resolved to a supported US listing with normalized SEC, market, and news evidence."
            ),
            thesis=(
                "The stage-C pipeline assembled a traceable evidence package. "
                "Investment analysis and ranking are intentionally deferred to stage D."
            ),
            supporting_evidence_ids=supporting_ids,
            risks=["Risk analysis is not implemented in the stage C skeleton."],
            invalidation_conditions=[
                "Required evidence becomes stale, unavailable, or conflicts with a newer primary filing."
            ],
            confidence="low",
        )
        return FinanceResearchResult(
            query=query,
            as_of=options.as_of,
            candidates=[candidate],
            evidence=evidence,
            warnings=["stage_c_fixture_pipeline_not_an_investment_recommendation"],
        )

    @staticmethod
    def _build_evidence(
        security: SecurityIdentifier,
        *,
        filings: list[SecFiling],
        facts: list[SecFact],
        market: MarketSnapshot,
        news: list[NewsItem],
        retrieved_at: datetime,
    ) -> list[FinancialEvidence]:
        evidence: list[FinancialEvidence] = []
        for filing in filings:
            evidence.append(
                FinancialEvidence(
                    evidence_id=f"{security.ticker}-filing-{filing.accession_number}",
                    security=security,
                    evidence_type="filing",
                    reporting_period=(
                        filing.report_date.isoformat() if filing.report_date else None
                    ),
                    published_at=_date_as_utc(filing.filed_at),
                    effective_at=_date_as_utc(filing.report_date),
                    retrieved_at=retrieved_at,
                    source_type="sec_filing",
                    source_url=filing.filing_url,
                    authority_level="primary",
                    content=f"{filing.form} filed on {filing.filed_at.isoformat()}.",
                )
            )
        for fact in facts:
            evidence.append(
                FinancialEvidence(
                    evidence_id=(
                        f"{security.ticker}-fact-{fact.concept}-"
                        f"{fact.period_end.isoformat()}-{fact.filed_at.isoformat()}"
                    ),
                    security=security,
                    evidence_type="fundamental",
                    metric_name=fact.label,
                    value=fact.value,
                    unit=fact.unit,
                    currency="USD" if fact.unit == "USD" else None,
                    reporting_period=(
                        f"FY{fact.fiscal_year}-{fact.fiscal_period}"
                        if fact.fiscal_year and fact.fiscal_period
                        else fact.period_end.isoformat()
                    ),
                    published_at=_date_as_utc(fact.filed_at),
                    effective_at=_date_as_utc(fact.period_end),
                    retrieved_at=retrieved_at,
                    source_type="sec_xbrl",
                    source_url=(
                        "https://data.sec.gov/api/xbrl/companyfacts/"
                        f"CIK{security.cik}.json"
                    ),
                    authority_level="primary",
                    content=f"{fact.label}: {fact.value} {fact.unit}.",
                )
            )
        evidence.append(
            FinancialEvidence(
                evidence_id=(
                    f"{security.ticker}-market-{market.observed_at.isoformat()}"
                ),
                security=security,
                evidence_type="market",
                metric_name="Market price",
                value=market.price,
                unit=market.currency,
                currency=market.currency,
                published_at=market.observed_at,
                effective_at=market.observed_at,
                retrieved_at=market.retrieved_at,
                source_type="google_finance",
                source_url=market.source_url,
                authority_level="market_data",
                content=f"Observed market price: {market.price} {market.currency}.",
            )
        )
        for index, item in enumerate(news[:3], start=1):
            evidence.append(
                FinancialEvidence(
                    evidence_id=f"{security.ticker}-news-{index}",
                    security=security,
                    evidence_type="news",
                    published_at=item.published_at,
                    effective_at=item.published_at,
                    retrieved_at=item.retrieved_at,
                    source_type="google_news",
                    source_url=item.url,
                    authority_level="news",
                    content=f"{item.title}. {item.snippet}".strip(),
                )
            )
        return evidence
