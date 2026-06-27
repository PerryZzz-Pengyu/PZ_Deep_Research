from __future__ import annotations

from app.agent.tools.registry import ToolRegistry
from app.agent.tools.visit import VisitTool
from app.config import Settings
from app.research.domains.academic.search import SearchTool


def build_academic_tool_registry(
    settings: Settings,
    *,
    search_api_key_override: str | None = None,
    reader_api_key_override: str | None = None,
) -> ToolRegistry:
    search_api_key = search_api_key_override or settings.serpapi_api_key
    search_provider = "serpapi" if search_api_key_override else settings.search_provider
    return ToolRegistry(
        [
            SearchTool(
                provider=search_provider,
                serpapi_api_key=search_api_key,
                academic_engine=settings.academic_search_engine,
            ),
            VisitTool(
                jina_api_key=reader_api_key_override or settings.jina_api_key,
                max_concurrency=settings.visit_max_concurrency,
            ),
        ]
    )
