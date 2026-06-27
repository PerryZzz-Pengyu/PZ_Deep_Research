from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from datetime import date, datetime, time, timezone
from typing import Any, Protocol

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


_PLANNER_SYSTEM_PROMPT = (
    "You are a US equity research planner. Given the user's query, identify 1-3 US stock "
    "tickers (NYSE, Nasdaq, or NYSE American listed) that should be researched. "
    "Respond ONLY with valid JSON: {\"tickers\": [\"TICKER1\"]}. No explanations."
)

_REPORT_SYSTEM_PROMPT = (
    "你是一位专业的美股基本面研究分析师。请基于以下证据，用中文撰写一份研究报告。\n"
    "报告需包含：研究对象与入选理由、核心基本面数据与来源、市场表现、近期新闻动态、"
    "风险与注意事项。结尾必须注明：「本报告仅供信息研究与学习参考，不构成投资建议。」"
)


def _date_as_utc(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _parse_planner_json(content: str) -> list[str]:
    match = re.search(r'\{[^{}]*"tickers"[^{}]*\}', content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            tickers = data.get("tickers", [])
            return [t.strip().upper() for t in tickers if isinstance(t, str)][:3]
        except (json.JSONDecodeError, AttributeError):
            pass
    return []


def _text_chunks(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i : i + size]


class FinanceRuntime:
    """Stage-C named-security fixture pipeline; Stage-D SSE event generator."""

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
        provider_factory: Any | None = None,
        report_model: str = "",
    ) -> None:
        self.security_resolver = security_resolver
        self.sec_connector = sec_connector
        self.market_connector = market_connector
        self.news_connector = news_connector
        self.provider_factory = provider_factory
        self.report_model = report_model

    # ── Stage D: SSE event generator ───────────────────────────────────────

    async def run(self, job_id: str, request: Any) -> AsyncIterator[Any]:
        from app.agent.schemas import LLMMessage, ResearchEvent

        if self.provider_factory is None:
            raise RuntimeError("FinanceRuntime.provider_factory must be set to use run()")

        provider = self.provider_factory.create(
            request.provider,
            api_key=getattr(request, "api_key", None),
            base_url=getattr(request, "base_url", None),
        )
        as_of = datetime.now(timezone.utc)
        options = FinanceOptions(as_of=as_of)

        yield ResearchEvent(
            job_id=job_id,
            type="status",
            message="开始美股基本面研究",
            payload={"domain": "finance", "provider": provider.name, "mode": request.mode},
        )

        # ── Step 1: Planner ─────────────────────────────────────────────
        if provider.name == "mock":
            # For mock: use the first token of the query directly as a ticker
            raw = request.query.strip().split()[0].upper() if request.query.strip() else "AAPL"
            tickers = [raw]
        else:
            yield ResearchEvent(
                job_id=job_id,
                type="llm_start",
                message="Planner 解析研究对象",
                payload={"stage": "plan"},
            )
            try:
                planner_messages = [
                    LLMMessage(role="system", content=_PLANNER_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=request.query),
                ]
                planner_result = await provider.generate(
                    planner_messages,
                    model=request.model,
                    temperature=0.0,
                )
                tickers = _parse_planner_json(planner_result.content)
            except Exception as exc:
                yield ResearchEvent(
                    job_id=job_id,
                    type="failed",
                    message=f"Planner 调用失败: {exc}",
                    payload={
                        "error_code": "planner_error",
                        "error_stage": "plan",
                        "error_retryable": True,
                    },
                )
                return
            yield ResearchEvent(
                job_id=job_id,
                type="llm_result",
                message="Planner 完成",
                payload={"tickers": tickers},
            )

        if not tickers:
            yield ResearchEvent(
                job_id=job_id,
                type="failed",
                message="未能识别研究对象，请提供明确的公司名或股票代码",
                payload={
                    "error_code": "no_tickers_identified",
                    "error_stage": "plan",
                    "error_retryable": False,
                },
            )
            return

        # ── Step 2: Evidence per ticker ──────────────────────────────────
        all_results: list[FinanceResearchResult] = []
        for ticker in tickers[:3]:
            yield ResearchEvent(
                job_id=job_id,
                type="status",
                message=f"获取 {ticker} 数据",
                payload={"ticker": ticker},
            )
            try:
                result = await self.research(ticker, options=options)
                all_results.append(result)
                yield ResearchEvent(
                    job_id=job_id,
                    type="evidence_ready",
                    message=f"{ticker} 数据获取完成",
                    payload={"ticker": ticker, "evidence_count": len(result.evidence)},
                )
            except Exception as exc:
                yield ResearchEvent(
                    job_id=job_id,
                    type="status",
                    message=f"跳过 {ticker}：{exc}",
                    payload={"ticker": ticker, "warning": str(exc)},
                )

        if not all_results:
            yield ResearchEvent(
                job_id=job_id,
                type="failed",
                message="未找到可研究的证券",
                payload={
                    "error_code": "no_securities_found",
                    "error_stage": "evidence",
                    "error_retryable": False,
                },
            )
            return

        # ── Step 3: Report ───────────────────────────────────────────────
        yield ResearchEvent(
            job_id=job_id,
            type="status",
            message="正在撰写研究报告",
            payload={},
        )

        if provider.name == "mock":
            canned = self._build_mock_report(all_results, request)
            for chunk in _text_chunks(canned, 30):
                yield ResearchEvent(
                    job_id=job_id,
                    type="report_delta",
                    message="",
                    payload={"delta": chunk},
                )
        else:
            report_model = self.report_model or request.model
            async for delta in self._stream_finance_report(
                provider, report_model, all_results, request
            ):
                yield ResearchEvent(
                    job_id=job_id,
                    type="report_delta",
                    message="",
                    payload={"delta": delta},
                )

        sources = [
            {"url": ev.source_url, "title": ev.metric_name or ev.evidence_type}
            for result in all_results
            for ev in result.evidence
            if ev.source_url
        ][:10]

        yield ResearchEvent(
            job_id=job_id,
            type="completed",
            message="美股研究报告已完成",
            payload={"final_report": "", "sources": sources},
        )

    async def resume_report(
        self,
        job_id: str,
        request: Any,
        retry_context: dict[str, Any],
    ) -> AsyncIterator[Any]:
        # Finance MVP: no checkpoint-based resume; restart the full pipeline.
        async for event in self.run(job_id, request):
            yield event

    # ── Stage C: named-security fixture pipeline ────────────────────────

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

    # ── Helpers ─────────────────────────────────────────────────────────

    def _build_mock_report(self, results: list[FinanceResearchResult], request: Any) -> str:
        tickers = [r.candidates[0].security.ticker for r in results if r.candidates]
        ticker_str = "、".join(tickers) if tickers else "相关股票"
        return (
            f"## 美股研究摘要（开发模式演示）\n\n"
            f"**研究对象：** {ticker_str}\n\n"
            f"**用户问题：** {request.query}\n\n"
            f"## 免责声明\n\n"
            f"本报告仅供信息研究与学习参考，不构成投资建议。"
            f"当前使用 mock provider，不代表真实研究分析结果。\n"
            f"配置 OpenAI API Key 后，可以切换到真实金融数据分析。\n"
        )

    async def _stream_finance_report(
        self,
        provider: Any,
        model: str,
        results: list[FinanceResearchResult],
        request: Any,
    ) -> AsyncIterator[str]:
        from app.agent.schemas import LLMMessage

        evidence_lines: list[str] = []
        for result in results:
            if result.candidates:
                sec = result.candidates[0].security
                evidence_lines.append(
                    f"### {sec.company_name} ({sec.ticker}, {sec.exchange})"
                )
            for ev in result.evidence[:5]:
                evidence_lines.append(f"- [{ev.evidence_type}] {ev.content}")

        messages = [
            LLMMessage(role="system", content=_REPORT_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"用户问题：{request.query}\n\n"
                    f"证据材料：\n{''.join(evidence_lines)}"
                ),
            ),
        ]
        yielded_any = False
        async for chunk in provider.stream_generate(messages, model=model):
            if chunk.type == "delta" and chunk.delta:
                yielded_any = True
                yield chunk.delta
            elif chunk.type == "done" and chunk.result and not yielded_any:
                # Provider that doesn't emit delta chunks (e.g. MockProvider)
                if chunk.result.content:
                    yield chunk.result.content

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
