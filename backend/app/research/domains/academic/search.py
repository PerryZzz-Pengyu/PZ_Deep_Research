from __future__ import annotations

"""Google Scholar search implementation owned by the academic domain."""

from typing import Any

import httpx

from app.agent.schemas import ToolResult
from app.agent.tools.base import AgentTool
from app.agent.tools.utils import add_unique_source, normalize_string_list


class SearchTool(AgentTool):
    name = "search"
    description = "搜索公开网页资料，默认聚焦 Google Scholar 学术结果。"

    def __init__(
        self,
        *,
        provider: str = "serpapi",
        serpapi_api_key: str = "",
        academic_engine: str = "google_scholar",
        serpapi_endpoint: str = "https://serpapi.com/search",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider.strip().lower() or "serpapi"
        self.serpapi_api_key = serpapi_api_key.strip()
        self.academic_engine = academic_engine.strip() or "google_scholar"
        self.serpapi_endpoint = serpapi_endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        queries = normalize_string_list(arguments, "query", "queries")
        if not queries:
            return ToolResult(name=self.name, content="[search] 缺少 query 参数")

        if self.provider == "serpapi":
            return await self._call_serpapi(queries)
        if self.provider == "mock":
            content = "\n".join(
                f"开发模式学术搜索结果：SEARCH_PROVIDER=mock，暂不真实搜索。待搜索词：{query}"
                for query in queries
            )
            return ToolResult(
                name=self.name,
                content=content,
                sources=[
                    {
                        "title": "开发模式占位来源",
                        "url": "https://example.com/pz-deep-research",
                        "read_status": "mock",
                        "evidence_level": "mock",
                        "evidence_note": "开发模式占位来源，不代表真实证据。",
                    }
                ],
            )

        content = "\n".join(
            f"开发模式搜索结果：SEARCH_PROVIDER={self.provider} 不支持，无法真实搜索。待搜索词：{query}"
            for query in queries
        )
        return ToolResult(
            name=self.name,
            content=content,
            sources=[
                {
                    "title": "开发模式占位来源",
                    "url": "https://example.com/pz-deep-research",
                    "read_status": "mock",
                    "evidence_level": "mock",
                    "evidence_note": "开发模式占位来源，不代表真实证据。",
                }
            ],
        )

    async def _call_serpapi(self, queries: list[str]) -> ToolResult:
        if not self.serpapi_api_key:
            content = "\n".join(
                f"开发模式学术搜索结果：暂未配置 SERPAPI_API_KEY，无法真实搜索。待搜索词：{query}"
                for query in queries
            )
            return ToolResult(
                name=self.name,
                content=content,
                sources=[
                    {
                        "title": "开发模式占位来源",
                        "url": "https://example.com/pz-deep-research",
                        "read_status": "mock",
                        "evidence_level": "mock",
                        "evidence_note": "开发模式占位来源，不代表真实证据。",
                    }
                ],
            )

        responses: list[str] = []
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
            for query in queries:
                try:
                    response = await client.get(
                        self.serpapi_endpoint,
                        params={
                            "engine": self.academic_engine,
                            "q": query,
                            "api_key": self.serpapi_api_key,
                            "num": 10,
                            "as_sdt": 0,
                            "output": "json",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPError as exc:
                    responses.append(f"搜索词：{query}\n搜索失败：{exc}")
                    continue

                if data.get("error"):
                    responses.append(f"搜索词：{query}\n搜索失败：{data['error']}")
                    continue

                lines = [f"学术搜索词：{query}"]
                for index, item in enumerate(data.get("organic_results", [])[:10], start=1):
                    title = item.get("title", "")
                    url = self._scholar_result_url(item)
                    snippet = item.get("snippet", "")
                    publication = self._publication_summary(item)
                    citations = self._citation_count(item)
                    metadata_parts = [part for part in [publication, citations] if part]
                    metadata = f"\n学术信息: {'；'.join(metadata_parts)}" if metadata_parts else ""
                    lines.append(f"{index}. {title}\nURL: {url}\n摘要: {snippet}{metadata}")
                    add_unique_source(
                        sources,
                        seen_urls,
                        title=title or url,
                        url=url,
                        snippet=snippet,
                        query=query,
                        read_status="search_result",
                        evidence_level="metadata",
                        evidence_note="Google Scholar 题录和摘要，尚未阅读全文。",
                    )
                responses.append("\n".join(lines))

        return ToolResult(name=self.name, content="\n\n---\n\n".join(responses), sources=sources)

    @staticmethod
    def _scholar_result_url(item: dict[str, Any]) -> str:
        link = item.get("link")
        if isinstance(link, str) and link:
            return link
        resources = item.get("resources")
        if isinstance(resources, list):
            for resource in resources:
                if isinstance(resource, dict) and isinstance(resource.get("link"), str):
                    return resource["link"]
        result_id = item.get("result_id")
        if isinstance(result_id, str) and result_id:
            return f"https://scholar.google.com/scholar?cluster={result_id}"
        return ""

    @staticmethod
    def _publication_summary(item: dict[str, Any]) -> str:
        publication_info = item.get("publication_info")
        if not isinstance(publication_info, dict):
            return ""
        summary = publication_info.get("summary")
        return summary if isinstance(summary, str) else ""

    @staticmethod
    def _citation_count(item: dict[str, Any]) -> str:
        inline_links = item.get("inline_links")
        if not isinstance(inline_links, dict):
            return ""
        cited_by = inline_links.get("cited_by")
        if not isinstance(cited_by, dict):
            return ""
        total = cited_by.get("total")
        if isinstance(total, int):
            return f"引用 {total} 次"
        return ""
