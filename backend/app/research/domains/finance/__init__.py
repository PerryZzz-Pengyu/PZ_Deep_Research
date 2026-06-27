"""US-equity research domain contracts and stage-C/D runtime."""

from app.research.domains.finance.runtime import FinanceRuntime
from app.research.domains.finance.schemas import (
    FinanceOptions,
    FinanceResearchResult,
    FinancialEvidence,
    SecurityIdentifier,
)

__all__ = [
    "FinanceOptions",
    "FinanceResearchResult",
    "FinanceRuntime",
    "FinancialEvidence",
    "SecurityIdentifier",
    "build_finance_runtime",
]


def build_finance_runtime(settings: object) -> FinanceRuntime:
    """Construct a production-ready FinanceRuntime from application Settings."""
    from app.agent.providers import ProviderFactory
    from app.research.domains.finance.connectors.google_finance import GoogleFinanceConnector
    from app.research.domains.finance.connectors.google_news import GoogleNewsConnector
    from app.research.domains.finance.connectors.sec import (
        SecEdgarConnector,
        SecSecurityDirectoryConnector,
    )
    from app.research.domains.finance.security import CachedSecurityResolver

    user_agent = getattr(settings, "sec_user_agent", "") or "PZ-Deep-Research research@pz.ai"
    api_key = getattr(settings, "serpapi_api_key", "")
    report_model = getattr(settings, "openai_report_model", "")

    directory_connector = SecSecurityDirectoryConnector(user_agent=user_agent)
    resolver = CachedSecurityResolver(directory_connector=directory_connector)
    sec_connector = SecEdgarConnector(user_agent=user_agent)
    market_connector = GoogleFinanceConnector(api_key=api_key)
    news_connector = GoogleNewsConnector(api_key=api_key)

    return FinanceRuntime(
        provider_factory=ProviderFactory(settings),
        security_resolver=resolver,
        sec_connector=sec_connector,
        market_connector=market_connector,
        news_connector=news_connector,
        report_model=report_model,
    )
