from __future__ import annotations

import os
from typing import Any

import httpx

from app.agent.schemas import ToolResult
from app.agent.tools.base import AgentTool
from app.agent.tools.utils import add_unique_source, normalize_string_list


class SearchTool(AgentTool):
    name = "search"
    description = "搜索公开网页资料。"

    def __init__(
        self,
        api_key: str = "",
        *,
        endpoint: str = "https://google.serper.dev/search",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        queries = normalize_string_list(arguments, "query", "queries")
        if not queries:
            return ToolResult(name=self.name, content="[search] 缺少 query 参数")

        if not self.api_key:
            content = "\n".join(
                f"开发模式搜索结果：暂未配置 SERPER_API_KEY，无法真实搜索。待搜索词：{query}" for query in queries
            )
            return ToolResult(
                name=self.name,
                content=content,
                sources=[{"title": "开发模式占位来源", "url": "https://example.com/pz-deep-research"}],
            )

        responses: list[str] = []
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
            for query in queries:
                try:
                    response = await client.post(
                        self.endpoint,
                        headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                        json={"q": query, "num": 10},
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPError as exc:
                    responses.append(f"搜索词：{query}\n搜索失败：{exc}")
                    continue

                lines = [f"搜索词：{query}"]
                for index, item in enumerate(data.get("organic", [])[:10], start=1):
                    title = item.get("title", "")
                    url = item.get("link", "")
                    snippet = item.get("snippet", "")
                    lines.append(f"{index}. {title}\nURL: {url}\n摘要: {snippet}")
                    add_unique_source(
                        sources,
                        seen_urls,
                        title=title or url,
                        url=url,
                        snippet=snippet,
                        query=query,
                    )
                responses.append("\n".join(lines))

        return ToolResult(name=self.name, content="\n\n---\n\n".join(responses), sources=sources)
