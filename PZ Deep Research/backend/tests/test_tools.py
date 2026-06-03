from __future__ import annotations

import asyncio

import httpx

from app.agent.tools import ToolRegistry
from app.agent.tools.search import SearchTool
from app.agent.tools.visit import VisitTool


def test_search_tool_parses_serpapi_scholar_results_and_deduplicates_sources() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "title": "PZ Deep Research",
                        "link": "https://example.com/research",
                        "snippet": "一个面向 C 端的深度研究产品。",
                        "publication_info": {"summary": "PZ Team - Journal of Research, 2026"},
                        "inline_links": {"cited_by": {"total": 12}},
                    },
                    {
                        "title": "重复来源",
                        "link": "https://example.com/research",
                        "snippet": "重复 URL 应该被去重。",
                    },
                ]
            },
        )

    async def call_tool():
        tool = SearchTool(serpapi_api_key="serpapi-key", transport=httpx.MockTransport(handler))
        return await tool.call({"query": [" PZ Deep Research ", "", "PZ Deep Research"]})

    result = asyncio.run(call_tool())

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.params["engine"] == "google_scholar"
    assert requests[0].url.params["q"] == "PZ Deep Research"
    assert requests[0].url.params["api_key"] == "serpapi-key"
    assert result.name == "search"
    assert "PZ Deep Research" in result.content
    assert "PZ Team - Journal of Research, 2026" in result.content
    assert "引用 12 次" in result.content
    assert result.sources == [
        {
            "title": "PZ Deep Research",
            "url": "https://example.com/research",
            "snippet": "一个面向 C 端的深度研究产品。",
            "query": "PZ Deep Research",
        }
    ]


def test_search_tool_returns_failure_result_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "upstream failed"})

    async def call_tool():
        tool = SearchTool(serpapi_api_key="serpapi-key", transport=httpx.MockTransport(handler))
        return await tool.call({"query": "失败测试"})

    result = asyncio.run(call_tool())

    assert "搜索失败" in result.content
    assert result.sources == []


def test_visit_tool_reads_jina_content_and_records_source() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="网页正文：这里是可供 Agent 使用的证据片段。")

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=httpx.MockTransport(handler))
        return await tool.call(
            {
                "url": "http://example.com/article",
                "goal": "提取产品信息",
            }
        )

    result = asyncio.run(call_tool())

    assert len(requests) == 1
    assert str(requests[0].url) == "https://r.jina.ai/http://example.com/article"
    assert requests[0].headers["Authorization"] == "Bearer jina-key"
    assert "网页正文" in result.content
    assert result.sources == [
        {
            "title": "http://example.com/article",
            "url": "http://example.com/article",
        }
    ]


def test_visit_tool_rejects_unsupported_url_scheme() -> None:
    async def call_tool():
        tool = VisitTool()
        return await tool.call({"url": "file:///etc/passwd"})

    result = asyncio.run(call_tool())

    assert "不支持的 URL" in result.content
    assert result.sources == []


def test_tool_registry_returns_unknown_tool_result() -> None:
    async def call_registry():
        return await ToolRegistry([]).call("missing", {})

    result = asyncio.run(call_registry())

    assert result.name == "missing"
    assert "未知工具" in result.content
