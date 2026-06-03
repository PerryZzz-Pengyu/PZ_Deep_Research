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
        seen_source_urls: set[str] = set()
        used_tools: set[str] = set()
        real_provider_requires_evidence = provider.name in {"openai", "anthropic", "gemini"}
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
                    "content_preview": result.content.strip()[:1200],
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_estimated_cost_usd": round(total_estimated_cost_usd, 8),
                },
            )
            content = result.content.strip()

            answer = self._extract_answer(content)
            if answer:
                missing_evidence = self._missing_evidence_requirements(
                    request.mode,
                    used_tools,
                    real_provider_requires_evidence,
                )
                if missing_evidence:
                    yield ResearchEvent(
                        job_id=job_id,
                        type="evidence_required",
                        message="模型尝试直接生成报告，已要求继续检索证据",
                        payload={
                            "round": round_index,
                            "missing": missing_evidence,
                            "content_preview": answer[:1000],
                        },
                    )
                    messages.append(
                        LLMMessage(
                            role="user",
                            content=self._build_evidence_request(request.mode, missing_evidence, collected_sources),
                        )
                    )
                    continue

                for chunk in self._chunk_text(answer):
                    yield ResearchEvent(
                        job_id=job_id,
                        type="report_delta",
                        message="正在生成研究报告",
                        payload={"delta": chunk},
                    )
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

            messages.append(LLMMessage(role="assistant", content=content))

            tool_name = tool_call.get("name", "")
            arguments = tool_call.get("arguments", {})
            used_tools.add(tool_name)
            yield ResearchEvent(
                job_id=job_id,
                type="tool_start",
                message=f"调用工具：{tool_name}",
                payload={"tool": tool_name, "arguments": arguments},
            )
            tool_result = await self.tool_registry.call(tool_name, arguments)
            new_sources = self._merge_sources(collected_sources, seen_source_urls, tool_result.sources)
            yield ResearchEvent(
                job_id=job_id,
                type="tool_result",
                message=f"工具返回：{tool_name}",
                payload={
                    "tool": tool_result.name,
                    "content": tool_result.content,
                    "sources": new_sources,
                    "all_sources": collected_sources,
                },
            )
            source_context = self._format_sources_for_model(new_sources or collected_sources)
            messages.append(
                LLMMessage(
                    role="user",
                    content=f"<tool_response>\n{tool_result.content}\n\n{source_context}\n</tool_response>",
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

    @staticmethod
    def _missing_evidence_requirements(mode: str, used_tools: set[str], enabled: bool) -> list[str]:
        if not enabled:
            return []
        missing: list[str] = []
        if "search" not in used_tools:
            missing.append("search")
        if mode in {"deep", "expert"} and "visit" not in used_tools:
            missing.append("visit")
        return missing

    @staticmethod
    def _build_evidence_request(
        mode: str,
        missing_evidence: list[str],
        collected_sources: list[dict[str, str]],
    ) -> str:
        source_context = AgentRuntime._format_sources_for_model(collected_sources)
        if "search" in missing_evidence:
            return (
                "你还不能输出 <answer>。请先调用 search 获取 Google Scholar 学术来源。"
                "请使用 2-4 个英文检索词，覆盖疗效、安全性和适用人群。"
            )
        if "visit" in missing_evidence:
            return (
                "你还不能输出 <answer>。deep/expert 模式需要先调用 visit 阅读关键来源。"
                "请从下面可引用来源中选择最相关的 1-3 个 URL 访问。\n"
                f"{source_context}"
            )
        return f"请继续研究。当前模式：{mode}。"

    @staticmethod
    def _merge_sources(
        collected_sources: list[dict[str, str]],
        seen_source_urls: set[str],
        sources: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        new_sources: list[dict[str, str]] = []
        for source in sources:
            url = source.get("url", "")
            if not url or url in seen_source_urls:
                continue
            seen_source_urls.add(url)
            citation_id = str(len(collected_sources) + 1)
            enriched = dict(source)
            enriched["citation_id"] = citation_id
            collected_sources.append(enriched)
            new_sources.append(enriched)
        return new_sources

    @staticmethod
    def _format_sources_for_model(sources: list[dict[str, str]]) -> str:
        if not sources:
            return "可引用来源：暂无。"
        lines = ["可引用来源："]
        for source in sources:
            citation_id = source.get("citation_id", "?")
            title = source.get("title", source.get("url", ""))
            url = source.get("url", "")
            snippet = source.get("snippet", "")
            query = source.get("query", "")
            detail_parts = [part for part in [snippet, f"检索词：{query}" if query else ""] if part]
            detail = f" - {'；'.join(detail_parts)}" if detail_parts else ""
            lines.append(f"[{citation_id}] {title}. {url}{detail}")
        return "\n".join(lines)

    @staticmethod
    def _chunk_text(text: str, size: int = 180) -> list[str]:
        if not text:
            return []
        return [text[index : index + size] for index in range(0, len(text), size)]
