from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.research.domains.finance.schemas import (
    FINANCE_METHODOLOGY_VERSION,
    FINANCE_RESULT_SCHEMA_VERSION,
    CandidateResearch,
    FinanceOptions,
    FinanceResearchResult,
    FinancialEvidence,
    MarketSnapshot,
    SecurityIdentifier,
)


AS_OF = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)


def make_security(ticker: str = "AAPL") -> SecurityIdentifier:
    return SecurityIdentifier(
        ticker=ticker,
        exchange="Nasdaq",
        cik="320193",
        company_name="Apple Inc.",
    )


def make_candidate(ticker: str) -> CandidateResearch:
    security = make_security(ticker)
    return CandidateResearch(
        security=security,
        selection_reason="Fixture-backed candidate",
        thesis="Public evidence package assembled.",
        supporting_evidence_ids=[f"{ticker}-market"],
        risks=["Risk analysis is not implemented in the stage C skeleton."],
        invalidation_conditions=["Required evidence becomes stale or unavailable."],
        confidence="low",
    )


def test_finance_options_define_bounded_us_equity_defaults() -> None:
    options = FinanceOptions(as_of=AS_OF)

    assert options.market == "US"
    assert options.horizon_months == 12
    assert options.max_initial_candidates == 10
    assert options.max_deep_dive_candidates == 5
    assert options.max_final_candidates == 3


def test_security_identifier_normalizes_ticker_and_cik() -> None:
    security = SecurityIdentifier(
        ticker="brk.b",
        exchange="NYSE",
        cik=1067983,
        company_name="Berkshire Hathaway Inc.",
    )

    assert security.ticker == "BRK-B"
    assert security.cik == "0001067983"


def test_financial_evidence_preserves_decimal_time_and_provenance() -> None:
    evidence = FinancialEvidence(
        evidence_id="aapl-revenue-2025",
        security=make_security(),
        evidence_type="fundamental",
        metric_name="Revenue",
        value=Decimal("391035000000"),
        unit="USD",
        currency="USD",
        reporting_period="FY2025",
        published_at=AS_OF,
        effective_at=AS_OF,
        retrieved_at=AS_OF,
        source_type="sec_xbrl",
        source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        authority_level="primary",
        content="Revenue reported in the filing.",
    )

    payload = evidence.model_dump(mode="json")

    assert payload["value"] == "391035000000"
    assert payload["published_at"] == "2026-06-28T12:00:00Z"
    assert "raw" not in payload


def test_finance_result_is_versioned_and_limited_to_three_candidates() -> None:
    result = FinanceResearchResult(
        query="large cap technology",
        as_of=AS_OF,
        candidates=[make_candidate("AAPL")],
        evidence=[],
    )

    assert result.schema_version == FINANCE_RESULT_SCHEMA_VERSION
    assert result.methodology_version == FINANCE_METHODOLOGY_VERSION
    assert "not investment advice" in result.disclaimer.lower()

    with pytest.raises(ValidationError):
        FinanceResearchResult(
            query="too many",
            as_of=AS_OF,
            candidates=[make_candidate(ticker) for ticker in ["A", "B", "C", "D"]],
            evidence=[],
        )


def test_finance_models_reject_timezone_naive_market_and_result_times() -> None:
    naive = datetime(2026, 6, 28, 12, 0)

    with pytest.raises(ValidationError):
        MarketSnapshot(
            security=make_security(),
            price=Decimal("201.25"),
            currency="USD",
            observed_at=naive,
            retrieved_at=AS_OF,
            source_url="https://www.google.com/finance/quote/AAPL:NASDAQ",
        )

    with pytest.raises(ValidationError):
        FinanceResearchResult(
            query="naive as-of",
            as_of=naive,
            candidates=[],
            evidence=[],
        )
