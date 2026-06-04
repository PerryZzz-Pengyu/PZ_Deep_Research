from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from app.agent.schemas import ToolResult
from app.agent.tools.base import AgentTool
from app.agent.tools.utils import is_supported_web_url, normalize_string_list


class VisitTool(AgentTool):
    name = "visit"
    description = "访问网页并提取与目标相关的信息。"

    def __init__(
        self,
        jina_api_key: str = "",
        *,
        reader_base_url: str = "https://r.jina.ai/",
        timeout_seconds: float = 45.0,
        max_content_chars: int = 20000,
        max_concurrency: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.jina_api_key = jina_api_key.strip()
        self.reader_base_url = reader_base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.max_content_chars = max_content_chars
        self.max_concurrency = max(1, max_concurrency)
        self.transport = transport

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        urls = normalize_string_list(arguments, "url", "urls")
        goal = str(arguments.get("goal", "") or "")
        if not urls:
            return ToolResult(name=self.name, content="[visit] 缺少 url 参数")

        # 滚动队列：最多 max_concurrency 个并发访问 Jina Reader，其余排队。
        # gather 按传入顺序返回结果，保证来源顺序 = URL 输入顺序，引用编号不乱。
        semaphore = asyncio.Semaphore(self.max_concurrency)
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            results = await asyncio.gather(
                *(self._fetch_one(client, url, goal, semaphore) for url in urls)
            )

        content_parts = [content for content, _, _ in results]
        sources = [source for _, source, _ in results if source is not None]
        # url -> 完整正文，供 Runtime 抽取证据卡片；不进入 sources 快照，避免污染事件/前端。
        source_texts = {source["url"]: text for _, source, text in results if source is not None}
        return ToolResult(
            name=self.name,
            content="\n\n---\n\n".join(content_parts),
            sources=sources,
            source_texts=source_texts,
        )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        url: str,
        goal: str,
        semaphore: asyncio.Semaphore,
    ) -> tuple[str, dict[str, str] | None, str]:
        """访问单个 URL，返回（工具文本片段, 来源字典或 None, 完整正文）。单条失败被本协程兜住，不影响其它。"""
        if not is_supported_web_url(url):
            return (f"不支持的 URL：{url}。visit 工具只允许 http/https 网页。", None, "")

        async with semaphore:
            if url.startswith("https://example.com/"):
                text = (
                    "开发模式网页内容：这是 PZ Deep Research 的占位网页访问结果。"
                    "真实环境中这里会返回网页正文、证据片段和摘要。"
                )
                read_status, evidence_level, evidence_note = "mock", "mock", "开发模式占位内容，不代表真实证据。"
            else:
                headers = {}
                if self.jina_api_key:
                    headers["Authorization"] = f"Bearer {self.jina_api_key}"
                try:
                    response = await client.get(f"{self.reader_base_url}{url}", headers=headers)
                    response.raise_for_status()
                    text = response.text[: self.max_content_chars]
                    read_status, evidence_level, evidence_note = self._classify_reader_text(text)
                except httpx.HTTPError as exc:
                    text = f"访问失败：{exc}"
                    read_status, evidence_level, evidence_note = "failed", "unavailable", "Reader 请求失败，不能作为证据使用。"

        source = self._build_source(
            url,
            text,
            read_status=read_status,
            evidence_level=evidence_level,
            evidence_note=evidence_note,
        )
        content = self._format_visit_content(
            goal=goal,
            url=url,
            text=text,
            read_status=read_status,
            evidence_level=evidence_level,
            evidence_note=evidence_note,
        )
        return (content, source, text)

    @staticmethod
    def _classify_reader_text(text: str) -> tuple[str, str, str]:
        normalized = text.lower()
        blocked_markers = [
            "target url returned error 403",
            "403: forbidden",
            "are you a robot",
            "captcha",
            "just a moment",
        ]
        if any(marker in normalized for marker in blocked_markers):
            return "blocked", "metadata_only", "Reader 返回 403、Forbidden 或 CAPTCHA 页面，不能当作已阅读全文。"
        if len(text.strip()) < 500:
            return "partial", "partial_text", "Reader 返回内容较短，只能作为部分正文证据。"
        return "full_text", "full_text", "Jina Reader 返回可用正文。"

    @staticmethod
    def _build_source(
        url: str,
        text: str,
        *,
        read_status: str,
        evidence_level: str,
        evidence_note: str,
    ) -> dict[str, str]:
        title = VisitTool._extract_title(text) or url
        return {
            "title": title,
            "url": url,
            "read_status": read_status,
            "evidence_level": evidence_level,
            "evidence_note": evidence_note,
            "content_preview": text.strip()[:500],
        }

    @staticmethod
    def _extract_title(text: str) -> str:
        for line in text.splitlines()[:12]:
            stripped = line.strip()
            if stripped.lower().startswith("title:"):
                return stripped.split(":", 1)[1].strip()
        return ""

    @staticmethod
    def _format_visit_content(
        *,
        goal: str,
        url: str,
        text: str,
        read_status: str,
        evidence_level: str,
        evidence_note: str,
    ) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc or url
        return (
            f"访问目标：{goal or '未指定'}\n"
            f"URL: {url}\n"
            f"域名：{domain}\n"
            f"读取状态：{read_status}\n"
            f"证据强度：{evidence_level}\n"
            f"状态说明：{evidence_note}\n"
            f"网页内容摘录：\n{text}"
        )
