from __future__ import annotations

from typing import Any

from app.agent.schemas import ToolResult
from app.agent.tools.base import AgentTool
from app.agent.tools.search import SearchTool
from app.agent.tools.visit import VisitTool
from app.config import Settings


class ToolRegistry:
    def __init__(self, tools: list[AgentTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(name=name, content=f"[tool] 未知工具：{name}")
        return await tool.call(arguments)

    def names(self) -> list[str]:
        return sorted(self._tools)


def build_default_tool_registry(settings: Settings) -> ToolRegistry:
    return ToolRegistry(
        [
            SearchTool(
                provider=settings.search_provider,
                serpapi_api_key=settings.serpapi_api_key,
                academic_engine=settings.academic_search_engine,
            ),
            VisitTool(
                jina_api_key=settings.jina_api_key,
                max_concurrency=settings.visit_max_concurrency,
            ),
        ]
    )
