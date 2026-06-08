from __future__ import annotations

import asyncio
import json
from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.schemas import LLMMessage, LLMResult


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, *, delay_seconds: float = 0.0) -> None:
        self.delay_seconds = max(delay_seconds, 0.0)

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)

        # 新流程下访问由 Runtime 驱动，模型只负责：被要求时输出 search 查询，
        # 或在收到「撰写最终研究报告」指令时输出 <answer>。
        last_user = next((message.content for message in reversed(messages) if message.role == "user"), "")

        if "撰写最终研究报告" not in last_user:
            query = last_user[:120].replace("\n", " ")
            payload = {"name": "search", "arguments": {"query": [query]}}
            return LLMResult(content=f"<tool_call>\n{json.dumps(payload, ensure_ascii=False)}\n</tool_call>", model="mock")

        return LLMResult(
            content=(
                "<answer>\n"
                "## 核心结论\n"
                "当前是 PZ Deep Research 的开发模式演示结果。Agent Runtime、工具调用协议、任务事件流和最终报告结构已经可以串起来。\n\n"
                "## 关键依据\n"
                "- 系统完成了搜索工具调用。\n"
                "- 系统完成了网页访问工具调用。\n"
                "- 系统根据工具结果生成了结构化报告。\n\n"
                "## 来源和证据\n"
                "- 开发模式使用 mock provider，不代表真实网页研究结果。\n\n"
                "## 注意事项\n"
                "配置 OpenAI、Anthropic 或 Gemini API Key 后，可以切换到真实模型 Provider。\n"
                "</answer>"
            ),
            model="mock",
        )
