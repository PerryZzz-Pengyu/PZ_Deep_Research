from __future__ import annotations

import asyncio

import httpx

from app.agent.tools import ToolRegistry, build_default_tool_registry
from app.agent.tools.search import SearchTool
from app.agent.tools.visit import VisitTool
from app.config import Settings


def test_default_tool_registry_uses_per_request_credentials() -> None:
    settings = Settings(
        search_provider="mock",
        serpapi_api_key="server-serpapi-key",
        jina_api_key="server-jina-key",
    )

    registry = build_default_tool_registry(
        settings,
        search_api_key_override="request-serpapi-key",
        reader_api_key_override="request-jina-key",
    )

    search = registry._tools["search"]
    visit = registry._tools["visit"]
    assert isinstance(search, SearchTool)
    assert isinstance(visit, VisitTool)
    assert search.provider == "serpapi"
    assert search.serpapi_api_key == "request-serpapi-key"
    assert visit.jina_api_key == "request-jina-key"


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
            "read_status": "search_result",
            "evidence_level": "metadata",
            "evidence_note": "Google Scholar 题录和摘要，尚未阅读全文。",
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
    reader_text = "网页正文：" + "这里是可供 Agent 使用的证据片段。" * 80

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=reader_text)

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
            "read_status": "full_text",
            "evidence_level": "full_text",
            "evidence_note": "Jina Reader 返回可用正文。",
            "content_preview": reader_text[:500],
        }
    ]


def test_visit_tool_marks_captcha_or_forbidden_page_as_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "Title: Just a moment...\n\n"
                "Warning: Target URL returned error 403: Forbidden\n"
                "Markdown Content:\n## Are you a robot?\nPlease complete the CAPTCHA."
            ),
        )

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=httpx.MockTransport(handler))
        return await tool.call({"url": "https://blocked.test/article", "goal": "读取证据"})

    result = asyncio.run(call_tool())

    assert "读取状态：blocked" in result.content
    assert result.sources == [
        {
            "title": "Just a moment...",
            "url": "https://blocked.test/article",
            "read_status": "blocked",
            "evidence_level": "metadata_only",
            "evidence_note": "Reader 返回 403、Forbidden 或 CAPTCHA 页面，不能当作已阅读全文。",
            "content_preview": "Title: Just a moment...\n\nWarning: Target URL returned error 403: Forbidden\nMarkdown Content:\n## Are you a robot?\nPlease complete the CAPTCHA.",
        }
    ]


class _ConcurrencyTrackingTransport(httpx.AsyncBaseTransport):
    """记录并发峰值，并可按 URL 定制延迟/失败，用于验证 visit 并发行为。"""

    def __init__(self, *, delay_by_path: dict[str, float] | None = None, default_delay: float = 0.05, fail_paths: set[str] | None = None) -> None:
        self.delay_by_path = delay_by_path or {}
        self.default_delay = default_delay
        self.fail_paths = fail_paths or set()
        self.current = 0
        self.peak = 0
        self.completion_order: list[str] = []
        self._lock = asyncio.Lock()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # r.jina.ai/<target>，取目标 URL 的路径尾段作为标识
        target = str(request.url).split("https://r.jina.ai/", 1)[-1]
        async with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)
        try:
            await asyncio.sleep(self.delay_by_path.get(target, self.default_delay))
            if target in self.fail_paths:
                raise httpx.ConnectError("模拟连接失败", request=request)
            self.completion_order.append(target)
            return httpx.Response(200, text="网页正文：" + "可用证据片段。" * 80)
        finally:
            async with self._lock:
                self.current -= 1


def test_visit_tool_visits_urls_concurrently_up_to_limit() -> None:
    transport = _ConcurrencyTrackingTransport(default_delay=0.05)
    urls = [f"https://example.org/a{i}" for i in range(10)]

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=transport, max_concurrency=5)
        return await tool.call({"url": urls, "goal": "并发测试"})

    result = asyncio.run(call_tool())

    # 10 个来源都返回，且并发峰值正好达到上限 5（证明既并发又被限流）
    assert len(result.sources) == 10
    assert transport.peak == 5


def test_visit_tool_respects_configurable_concurrency_limit() -> None:
    transport = _ConcurrencyTrackingTransport(default_delay=0.05)
    urls = [f"https://example.org/b{i}" for i in range(6)]

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=transport, max_concurrency=2)
        return await tool.call({"url": urls, "goal": "并发上限测试"})

    asyncio.run(call_tool())

    assert transport.peak <= 2


def test_visit_tool_preserves_source_order_regardless_of_completion() -> None:
    # 让第一个 URL 最慢、最后一个最快，完成顺序会被打乱，但来源必须保持输入顺序
    transport = _ConcurrencyTrackingTransport(
        delay_by_path={
            "https://example.org/first": 0.15,
            "https://example.org/middle": 0.08,
            "https://example.org/last": 0.01,
        }
    )
    urls = [
        "https://example.org/first",
        "https://example.org/middle",
        "https://example.org/last",
    ]

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=transport, max_concurrency=5)
        return await tool.call({"url": urls, "goal": "保序测试"})

    result = asyncio.run(call_tool())

    # 完成顺序确实被打乱（last 先于 first 完成）
    assert transport.completion_order[0] == "https://example.org/last"
    # 但返回的来源严格按输入顺序，保证引用编号不乱
    assert [source["url"] for source in result.sources] == urls


def test_visit_tool_isolates_per_url_errors() -> None:
    transport = _ConcurrencyTrackingTransport(
        default_delay=0.02,
        fail_paths={"https://example.org/broken"},
    )
    urls = [
        "https://example.org/ok1",
        "https://example.org/broken",
        "https://example.org/ok2",
    ]

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=transport, max_concurrency=5)
        return await tool.call({"url": urls, "goal": "错误隔离测试"})

    result = asyncio.run(call_tool())

    # 一个失败不影响其他；顺序保持，失败那条标记为 failed/unavailable
    assert [source["url"] for source in result.sources] == urls
    by_url = {source["url"]: source for source in result.sources}
    assert by_url["https://example.org/broken"]["read_status"] == "failed"
    assert by_url["https://example.org/broken"]["evidence_level"] == "unavailable"
    assert by_url["https://example.org/ok1"]["read_status"] == "full_text"
    assert by_url["https://example.org/ok2"]["read_status"] == "full_text"


def test_visit_tool_exposes_full_text_via_source_texts() -> None:
    reader_text = "网页正文：" + "完整正文证据片段。" * 200  # 远长于 content_preview 的 500 字

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=reader_text)

    async def call_tool():
        tool = VisitTool(jina_api_key="jina-key", transport=httpx.MockTransport(handler))
        return await tool.call({"url": "http://example.org/full", "goal": "抽卡片用"})

    result = asyncio.run(call_tool())

    # source_texts 提供完整正文（供 Runtime 抽卡片），而 sources 里只保留 500 字预览
    assert result.source_texts["http://example.org/full"] == reader_text[:20000]
    assert len(result.source_texts["http://example.org/full"]) > 500
    assert result.sources[0]["content_preview"] == reader_text[:500]


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
