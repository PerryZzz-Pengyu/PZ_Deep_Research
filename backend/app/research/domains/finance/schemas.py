from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FINANCE_RESULT_SCHEMA_VERSION = "finance-result-v1"
FINANCE_METHODOLOGY_VERSION = "finance-methodology-v1"
FINANCE_DISCLAIMER = (
    "This material is generated from public information for research and educational "
    "reference only. It is not investment advice, a recommendation, or a promise of returns."
)

USExchange = Literal["Nasdaq", "NYSE", "NYSE American"]
EvidenceType = Literal["filing", "fundamental", "market", "news", "issuer"]
AuthorityLevel = Literal["primary", "official", "market_data", "news", "secondary"]


def _require_timezone(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class FinanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinanceOptions(FinanceModel):
    market: Literal["US"] = "US"
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon_months: int = Field(default=12, ge=6, le=18)
    max_initial_candidates: int = Field(default=10, ge=5, le=10)
    max_deep_dive_candidates: int = Field(default=5, ge=3, le=5)
    max_final_candidates: int = Field(default=3, ge=0, le=3)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value, field_name="as_of")


class SecurityIdentifier(FinanceModel):
    ticker: str = Field(min_length=1, max_length=16)
    exchange: USExchange
    cik: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")
    company_name: str = Field(min_length=1, max_length=300)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> str:
        return str(value).strip().upper().replace(".", "-")

    @field_validator("cik", mode="before")
    @classmethod
    def normalize_cik(cls, value: object) -> str:
        raw = str(value).strip()
        if not raw.isdigit() or len(raw) > 10:
            raise ValueError("CIK must contain at most 10 digits")
        return raw.zfill(10)


class SecFiling(FinanceModel):
    form: str
    accession_number: str
    filed_at: date
    report_date: date | None = None
    primary_document: str
    filing_url: str


class SecFact(FinanceModel):
    taxonomy: str
    concept: str
    label: str
    description: str = ""
    unit: str
    value: Decimal
    period_start: date | None = None
    period_end: date
    filed_at: date
    form: str
    accession_number: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None


class MarketSnapshot(FinanceModel):
    security: SecurityIdentifier
    price: Decimal
    previous_close: Decimal | None = None
    currency: str
    observed_at: datetime
    retrieved_at: datetime
    source_url: str

    @field_validator("observed_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime, info) -> datetime:
        return _require_timezone(value, field_name=info.field_name)


class NewsItem(FinanceModel):
    title: str
    url: str
    source_name: str
    snippet: str = ""
    published_at: datetime | None = None
    retrieved_at: datetime

    @field_validator("published_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone(value, field_name=info.field_name)


class FinancialEvidence(FinanceModel):
    evidence_id: str = Field(min_length=1, max_length=200)
    security: SecurityIdentifier
    evidence_type: EvidenceType
    metric_name: str | None = None
    value: Decimal | None = None
    unit: str | None = None
    currency: str | None = None
    reporting_period: str | None = None
    published_at: datetime | None = None
    effective_at: datetime | None = None
    retrieved_at: datetime
    source_type: str
    source_url: str
    authority_level: AuthorityLevel
    content: str

    @field_validator("published_at", "effective_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone(value, field_name=info.field_name)


class CandidateResearch(FinanceModel):
    security: SecurityIdentifier
    selection_reason: str
    thesis: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    risk_evidence_ids: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"


class FinanceResearchResult(FinanceModel):
    schema_version: Literal["finance-result-v1"] = FINANCE_RESULT_SCHEMA_VERSION
    methodology_version: Literal["finance-methodology-v1"] = FINANCE_METHODOLOGY_VERSION
    query: str
    as_of: datetime
    candidates: list[CandidateResearch] = Field(default_factory=list, max_length=3)
    evidence: list[FinancialEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = FINANCE_DISCLAIMER

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value, field_name="as_of")
