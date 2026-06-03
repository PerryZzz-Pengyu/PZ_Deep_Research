from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any, Optional

from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.agent.providers import ProviderFactory
from app.agent.schemas import LLMMessage, ResearchEvent, ResearchRequest
from app.agent.tools import ToolRegistry


TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
ANSWER_PATTERN = re.compile(r"<answer>\s*(.*?)\s*</answer>", re.DOTALL)


class AgentRuntime:
    def __init__(
        self,
        provider_factory: ProviderFactory,
        tool_registry: ToolRegistry,
        *,
        max_llm_retries: int = 1,
        llm_timeout_seconds: float = 60.0,
    ) -> None:
        self.provider_factory = provider_factory
        self.tool_registry = tool_registry
        self.max_llm_retries = max(0, max_llm_retries)
        self.llm_timeout_seconds = max(0.1, llm_timeout_seconds)

    async def run(self, job_id: str, request: ResearchRequest) -> AsyncIterator[ResearchEvent]:
        provider_name = request.provider
        provider = self.provider_factory.create(provider_name)
        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_user_prompt(request.query, request.mode)),
        ]
        max_rounds = {"quick": 4, "deep": 8, "expert": 12}[request.mode]

        yield ResearchEvent(
            job_id=job_id,
            type="status",
            message="开始理解问题并制定研究计划",
            payload={"provider": provider.name, "mode": request.mode},
        )

        collected_sources: list[dict[str, str]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_estimated_cost_usd = 0.0
        for round_index in range(1, max_rounds + 1):
            yield ResearchEvent(
                job_id=job_id,
                type="llm_start",
                message=f"第 {round_index} 轮模型推理",
                payload={"round": round_index},
            )
            result = None
            for attempt in range(self.max_llm_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        provider.generate(messages, model=request.model),
                        timeout=self.llm_timeout_seconds,
                    )
                    break
                except TimeoutError as exc:
                    error_message = f"模型调用超时（超过 {self.llm_timeout_seconds:g} 秒）"
                    last_error: Exception = exc
                except Exception as exc:
                    error_message = f"模型调用失败：{exc}"
                    last_error = exc

                if attempt < self.max_llm_retries:
                    yield ResearchEvent(
                        job_id=job_id,
                        type="llm_retry",
                        message=f"{error_message}，准备重试",
                        payload={
                            "round": round_index,
                            "attempt": attempt + 1,
                            "max_retries": self.max_llm_retries,
                            "provider": provider.name,
                            "error": str(last_error),
                        },
                    )
                    continue

                yield ResearchEvent(
                    job_id=job_id,
                    type="failed",
                    message=f"研究任务失败：{error_message}",
                    payload={
                        "round": round_index,
                        "attempts": attempt + 1,
                        "provider": provider.name,
                        "error": str(last_error),
                    },
                )
                return

            if result is None:
                yield ResearchEvent(
                    job_id=job_id,
                    type="failed",
                    message="研究任务失败：模型没有返回结果",
                    payload={"round": round_index, "provider": provider.name},
                )
                return

            if result.input_tokens is not None:
                total_input_tokens += result.input_tokens
            if result.output_tokens is not None:
                total_output_tokens += result.output_tokens
            if result.estimated_cost_usd is not None:
                total_estimated_cost_usd += result.estimated_cost_usd
            yield ResearchEvent(
                job_id=job_id,
                type="llm_result",
                message=f"第 {round_index} 轮模型返回",
                payload={
                    "round": round_index,
                    "provider": provider.name,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_estimated_cost_usd": round(total_estimated_cost_usd, 8),
                },
            )
            content = result.content.strip()
            messages.append(LLMMessage(role="assistant", content=content))

            answer = self._extract_answer(content)
            if answer:
                yield ResearchEvent(
                    job_id=job_id,
                    type="completed",
                    message="研究报告已生成",
                    payload={"final_report": answer, "sources": collected_sources},
                )
                return

            tool_call = self._extract_tool_call(content)
            if not tool_call:
                yield ResearchEvent(
                    job_id=job_id,
                    type="warning",
                    message="模型未返回可识别的工具调用或最终答案，继续尝试",
                    payload={"round": round_index, "content": content[:1000]},
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="请继续研究。如果需要工具，请输出 <tool_call>；如果可以回答，请输出 <answer>。",
                    )
                )
                continue

            tool_name = tool_call.get("name", "")
            arguments = tool_call.get("arguments", {})
            yield ResearchEvent(
                job_id=job_id,
                type="tool_start",
                message=f"调用工具：{tool_name}",
                payload={"tool": tool_name, "arguments": arguments},
            )
            tool_result = await self.tool_registry.call(tool_name, arguments)
            collected_sources.extend(tool_result.sources)
            yield ResearchEvent(
                job_id=job_id,
                type="tool_result",
                message=f"工具返回：{tool_name}",
                payload={
                    "tool": tool_result.name,
                    "content": tool_result.content,
                    "sources": tool_result.sources,
                },
            )
            messages.append(
                LLMMessage(
                    role="user",
                    content=f"<tool_response>\n{tool_result.content}\n</tool_response>",
                )
            )

        yield ResearchEvent(
            job_id=job_id,
            type="completed",
            message="达到最大研究轮数，生成阶段性报告",
            payload={
                "final_report": "已达到当前模式的最大研究轮数。请切换更深模式或调整问题后重新运行。",
                "sources": collected_sources,
            },
        )

    @staticmethod
    def _extract_tool_call(content: str) -> Optional[dict[str, Any]]:
        match = TOOL_CALL_PATTERN.search(content)
        if not match:
            return None
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    @staticmethod
    def _extract_answer(content: str) -> Optional[str]:
        match = ANSWER_PATTERN.search(content)
        if not match:
            return None
        answer = match.group(1).strip()
        return answer or None
