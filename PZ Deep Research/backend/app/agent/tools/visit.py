from __future__ import annotations

import os
from typing import Any

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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.jina_api_key = jina_api_key or os.getenv("JINA_API_KEY", "")
        self.reader_base_url = reader_base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.max_content_chars = max_content_chars
        self.transport = transport

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        urls = normalize_string_list(arguments, "url", "urls")
        goal = arguments.get("goal", "")
        if not urls:
            return ToolResult(name=self.name, content="[visit] 缺少 url 参数")

        content_parts: list[str] = []
        sources: list[dict[str, str]] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            for url in urls:
                if not is_supported_web_url(url):
                    content_parts.append(f"不支持的 URL：{url}。visit 工具只允许 http/https 网页。")
                    continue

                if url.startswith("https://example.com/"):
                    text = (
                        "开发模式网页内容：这是 PZ Deep Research 的占位网页访问结果。"
                        "真实环境中这里会返回网页正文、证据片段和摘要。"
                    )
                else:
                    headers = {}
                    if self.jina_api_key:
                        headers["Authorization"] = f"Bearer {self.jina_api_key}"
                    try:
                        response = await client.get(f"{self.reader_base_url}{url}", headers=headers)
                        response.raise_for_status()
                        text = response.text[: self.max_content_chars]
                    except httpx.HTTPError as exc:
                        content_parts.append(f"访问失败：{url}\n错误：{exc}")
                        continue

                sources.append({"title": url, "url": url})
                content_parts.append(
                    f"访问目标：{goal or '未指定'}\nURL: {url}\n网页内容摘录：\n{text}"
                )

        return ToolResult(name=self.name, content="\n\n---\n\n".join(content_parts), sources=sources)
