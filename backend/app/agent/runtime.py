from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any, Optional

from app.agent.evidence import EvidenceCard, EvidenceExtractor, render_card
from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.agent.providers import ProviderFactory
from app.agent.schemas import LLMMessage, ResearchEvent, ResearchRequest
from app.agent.selection import count_full_text, select_sources, should_stop_visiting
from app.agent.tools import ToolRegistry


TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
ANSWER_PATTERN = re.compile(r"<answer>\s*(.*?)\s*</answer>", re.DOTALL)
TOOL_CALL_START_PATTERN = re.compile(r"<tool_call>\s*", re.DOTALL)
ANSWER_START_PATTERN = re.compile(r"<answer>\s*", re.DOTALL)

# Mock provider 用来判断"该出报告了"的稳定标记，必须与 _build_report_request 中的措辞一致。
REPORT_REQUEST_MARKER = "撰写最终研究报告"


MODE_POLICIES = {
    "quick": {
        "max_rounds": 8,
        "search_rounds": 1,
        "search_query_count": 1,
        "visit_source_count": 3,
        "full_text_source_count": 1,
        "min_report_chars": 400,
        "max_report_chars": 500,
        "report_style": "essay",
        "search_guidance": "Use exactly 1 high-intent English search query.",
        "visit_guidance": "Visit 3 key sources before answering.",
        "report_guidance": "Write an essay-style report with 400-500 Chinese body characters.",
    },
    "deep": {
        "max_rounds": 18,
        "search_rounds": 1,
        "search_query_count": 3,
        "visit_source_count": 10,
        "full_text_source_count": 3,
        "min_report_chars": 1300,
        "max_report_chars": 1500,
        "report_style": "literature_review",
        "search_guidance": "Use exactly 3 high-intent English search queries.",
        "visit_guidance": "Visit 10 key sources before answering.",
        "report_guidance": "Write a literature-review-style report with 1300-1500 Chinese body characters.",
    },
    "expert": {
        "max_rounds": 32,
        "search_rounds": 2,
        "search_query_count": 5,
        "visit_source_count": 20,
        "full_text_source_count": 5,
        "first_visit_source_count": 10,
        "min_report_chars": 3000,
        "max_report_chars": 3500,
        "report_style": "paper",
        "search_guidance": "Use exactly 5 high-intent English search queries in each search stage.",
        "visit_guidance": "Visit 20 key sources in total before the final answer.",
        "report_guidance": "Write a paper-style final report with 3000-3500 Chinese body characters.",
    },
}


class TagContentStream:
    def __init__(self, start_tag: str, end_tag: str) -> None:
        self.start_tag = start_tag
        self.end_tag = end_tag
        self.buffer = ""
        self.inside = False
        self.closed = False

    def feed(self, delta: str) -> str:
        if self.closed:
            return ""
        self.buffer += delta
        output = ""
        while self.buffer:
            if not self.inside:
                start_index = self.buffer.find(self.start_tag)
                if start_index < 0:
                    self.buffer = self.buffer[-(len(self.start_tag) - 1) :]
                    break
                self.buffer = self.buffer[start_index + len(self.start_tag) :]
                self.inside = True

            end_index = self.buffer.find(self.end_tag)
            if end_index >= 0:
                output += self.buffer[:end_index]
                self.buffer = self.buffer[end_index + len(self.end_tag) :]
                self.closed = True
                break

            safe_length = max(0, len(self.buffer) - (len(self.end_tag) - 1))
            if safe_length:
                output += self.buffer[:safe_length]
                self.buffer = self.buffer[safe_length:]
            break
        return output

    def flush(self) -> str:
        if not self.inside or self.closed:
            return ""
        output = self.buffer
        self.buffer = ""
        return output


class AgentRuntime:
    def __init__(
        self,
        provider_factory: ProviderFactory,
        tool_registry: ToolRegistry,
        *,
        max_llm_retries: int = 1,
        llm_timeout_seconds: float = 60.0,
        evidence_extraction_model: str = "gpt-5-nano",
        evidence_extraction_concurrency: int = 5,
    ) -> None:
        self.provider_factory = provider_factory
        self.tool_registry = tool_registry
        self.max_llm_retries = max(0, max_llm_retries)
        self.llm_timeout_seconds = max(0.1, llm_timeout_seconds)
        self.evidence_extraction_model = evidence_extraction_model
        self.evidence_extraction_concurrency = max(1, evidence_extraction_concurrency)

    async def run(self, job_id: str, request: ResearchRequest) -> AsyncIterator[ResearchEvent]:
        provider = self.provider_factory.create(request.provider)
        mode_policy = MODE_POLICIES[request.mode]
        target = int(mode_policy["visit_source_count"])
        minimum_full_text = int(mode_policy["full_text_source_count"])
        search_query_count = int(mode_policy["search_query_count"])
        search_stages = int(mode_policy.get("search_rounds", 1))
        goal = request.query
        real_provider = provider.name in {"openai", "anthropic", "gemini"}
        # 抽取卡片用便宜模型；非 OpenAI Provider 没有 gpt-5-nano，退回主模型。
        extraction_model = self.evidence_extraction_model if provider.name == "openai" else request.model
        extractor = EvidenceExtractor(
            provider,
            model=extraction_model,
            max_concurrency=self.evidence_extraction_concurrency,
        )

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_user_prompt(request.query, request.mode)),
        ]
        usage = {"input": 0, "output": 0, "cost": 0.0}

        yield ResearchEvent(
            job_id=job_id,
            type="status",
            message="开始理解问题并制定研究计划",
            payload={"provider": provider.name, "mode": request.mode},
        )

        visited: list[dict[str, str]] = []  # 已访问来源，按访问顺序分配阿拉伯 citation_id
        raw_by_url: dict[str, str] = {}  # url -> 完整正文，任务级内存，仅用于抽卡片
        cards: list[EvidenceCard] = []
        searched_urls: set[str] = set()
        visited_urls: set[str] = set()
        round_index = 0

        # ===== 检索 + 访问阶段（quick/deep 1 轮，expert 2 轮）=====
        for stage in range(search_stages):
            round_index += 1
            holder: dict[str, Any] = {}
            async for event in self._model_round(
                provider, messages, request, job_id, round_index, usage,
                allow_report_stream=False, holder=holder,
            ):
                yield event
            result = holder.get("result")
            if result is None:
                return
            content = result.content.strip()
            messages.append(LLMMessage(role="assistant", content=content))

            queries = self._extract_search_queries(content, request.query, search_query_count)
            yield ResearchEvent(
                job_id=job_id,
                type="tool_start",
                message="调用工具：search",
                payload={"tool": "search", "arguments": {"query": queries}},
            )
            search_result = await self.tool_registry.call("search", {"query": queries})
            new_candidates = self._mark_search_candidates(search_result.sources, searched_urls)
            yield ResearchEvent(
                job_id=job_id,
                type="tool_result",
                message="工具返回：search",
                payload={
                    "tool": search_result.name,
                    "content": search_result.content,
                    "sources": self._source_snapshot(new_candidates),
                },
            )
            # 只把精简的候选清单喂回模型（无全文），控制 token。
            messages.append(
                LLMMessage(
                    role="user",
                    content=f"<tool_response>\n{search_result.content[:3000]}\n</tool_response>",
                )
            )

            stage_target = target
            if stage == 0 and search_stages > 1:
                stage_target = int(mode_policy.get("first_visit_source_count", target))

            queue = [source for source in new_candidates if source["url"] not in visited_urls]
            async for event in self._visit_funnel(
                queue,
                stage_target,
                visited,
                raw_by_url,
                visited_urls,
                goal,
                job_id,
            ):
                yield event

            pending = [source for source in visited if source["url"] not in {card.url for card in cards}]
            if pending:
                new_cards = await extractor.extract_many(pending, raw_by_url, goal=goal)
                cards.extend(new_cards)
                yield ResearchEvent(
                    job_id=job_id,
                    type="evidence_ready",
                    message="已为已访问来源抽取证据卡片",
                    payload={
                        "new_cards": len(new_cards),
                        "total_cards": len(cards),
                        "fallback_cards": sum(
                            1 for card in new_cards if card.extraction_status == "fallback"
                        ),
                    },
                )

            if stage + 1 < search_stages:
                review_cards = "\n\n".join(render_card(card) for card in cards)
                messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "<evidence_cards>\n"
                            f"{review_cards or '（第一阶段没有可用证据卡片）'}\n"
                            "</evidence_cards>\n"
                            f"{self._build_supplement_search_request(search_query_count)}"
                        ),
                    )
                )
                yield ResearchEvent(
                    job_id=job_id,
                    type="status",
                    message="正在审查第一阶段证据缺口，准备补充检索",
                    payload={
                        "stage": stage + 1,
                        "visited": len(visited),
                        "full_text": count_full_text(visited),
                        "evidence_cards": len(cards),
                    },
                )

        # ===== 选源：质量优先 → 数量补足 → 逃生降级 =====
        selection = select_sources(
            visited,
            target,
            minimum_full_text=minimum_full_text,
        )
        selected, selected_cards = self._renumber_selected_sources(selection.selected, cards)
        yield ResearchEvent(
            job_id=job_id,
            type="source_selected",
            message="已完成来源筛选",
            payload={
                "sources": self._source_snapshot(selected),
                "target": target,
                "selected_count": len(selected),
                "minimum_full_text": minimum_full_text,
                "total_available": selection.total_available,
                "full_text_count": selection.full_text_count,
                "degraded": selection.degraded,
                "full_text_shortfall": selection.full_text_shortfall,
            },
        )

        # ===== 报告阶段 =====
        messages.append(
            LLMMessage(
                role="user",
                content=self._build_report_request(request.mode, selected_cards, selection),
            )
        )
        report_attempts = 0
        min_body_chars = int(mode_policy["min_report_chars"])
        max_body_chars = int(mode_policy["max_report_chars"])
        while True:
            round_index += 1
            holder = {}
            async for event in self._model_round(
                provider, messages, request, job_id, round_index, usage,
                allow_report_stream=True, holder=holder,
            ):
                yield event
            result = holder.get("result")
            if result is None:
                return
            streamed_report = bool(holder.get("streamed_report"))
            content = result.content.strip()
            answer = self._extract_answer(content)

            if not answer:
                if report_attempts >= 2:
                    answer = content  # 兜底：直接用模型输出，避免卡死
                else:
                    report_attempts += 1
                    messages.append(LLMMessage(role="assistant", content=content))
                    messages.append(
                        LLMMessage(
                            role="user",
                            content="请用 <answer>...</answer> 包裹最终研究报告，正文引用只能使用 [1]、[2] 这种阿拉伯角标。",
                        )
                    )
                    continue

            body_char_count = self._count_report_body_chars(answer)
            missing_report_format = self._missing_report_format(
                answer,
                selected,
                real_provider,
                min_body_chars=min_body_chars,
                max_body_chars=max_body_chars,
            )
            if missing_report_format:
                if streamed_report:
                    yield ResearchEvent(
                        job_id=job_id,
                        type="report_reset",
                        message="报告草稿格式不合格，准备重写",
                        payload={"round": round_index},
                    )
                if report_attempts >= 2:
                    yield ResearchEvent(
                        job_id=job_id,
                        type="failed",
                        message="研究报告经过重写后仍未满足格式或字数要求",
                        payload={
                            "round": round_index,
                            "missing": missing_report_format,
                            "body_char_count": body_char_count,
                            "min_body_chars": min_body_chars,
                            "max_body_chars": max_body_chars,
                        },
                    )
                    return
                report_attempts += 1
                yield ResearchEvent(
                    job_id=job_id,
                    type="citation_required",
                    message="研究报告格式、引用或字数不合格，已要求模型重写",
                    payload={
                        "round": round_index,
                        "missing": missing_report_format,
                        "attempt": report_attempts,
                        "body_char_count": body_char_count,
                        "min_body_chars": min_body_chars,
                        "max_body_chars": max_body_chars,
                        "content_preview": answer[:1000],
                    },
                )
                messages.append(LLMMessage(role="assistant", content=content))
                messages.append(
                    LLMMessage(
                        role="user",
                        content=self._build_report_rewrite_request(
                            missing_report_format,
                            selected_cards,
                            min_body_chars=min_body_chars,
                            max_body_chars=max_body_chars,
                            body_char_count=body_char_count,
                        ),
                    )
                )
                continue

            if not streamed_report:
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
                payload={"final_report": answer, "sources": self._source_snapshot(selected)},
            )
            return

    async def _model_round(
        self,
        provider: Any,
        messages: list[LLMMessage],
        request: ResearchRequest,
        job_id: str,
        round_index: int,
        usage: dict[str, Any],
        *,
        allow_report_stream: bool,
        holder: dict[str, Any],
    ) -> AsyncIterator[ResearchEvent]:
        """执行一次模型流式调用，封装重试/超时/流式报告，结果写入 holder。"""
        yield ResearchEvent(
            job_id=job_id,
            type="llm_start",
            message=f"第 {round_index} 轮模型推理",
            payload={"round": round_index},
        )
        result = None
        streamed_report = False
        answer_stream = TagContentStream("<answer>", "</answer>")
        last_error: Exception | None = None
        error_message = ""
        for attempt in range(self.max_llm_retries + 1):
            try:
                stream = provider.stream_generate(messages, model=request.model)
                while True:
                    try:
                        stream_event = await asyncio.wait_for(stream.__anext__(), timeout=self.llm_timeout_seconds)
                    except StopAsyncIteration:
                        break
                    if stream_event.type == "delta" and stream_event.delta:
                        if allow_report_stream:
                            report_delta = answer_stream.feed(stream_event.delta)
                            if report_delta:
                                streamed_report = True
                                yield ResearchEvent(
                                    job_id=job_id,
                                    type="report_delta",
                                    message="正在生成研究报告",
                                    payload={"delta": report_delta, "streaming": True},
                                )
                        yield ResearchEvent(
                            job_id=job_id,
                            type="llm_delta",
                            message=f"第 {round_index} 轮模型流式输出",
                            payload={
                                "round": round_index,
                                "attempt": attempt + 1,
                                "provider": provider.name,
                                "delta": stream_event.delta,
                            },
                        )
                    elif stream_event.type == "done":
                        result = stream_event.result
                if allow_report_stream:
                    trailing = answer_stream.flush()
                    if trailing:
                        streamed_report = True
                        yield ResearchEvent(
                            job_id=job_id,
                            type="report_delta",
                            message="正在生成研究报告",
                            payload={"delta": trailing, "streaming": True},
                        )
                break
            except TimeoutError as exc:
                error_message = f"模型调用超时（超过 {self.llm_timeout_seconds:g} 秒）"
                last_error = exc
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
            holder["result"] = None
            return

        if result is None:
            yield ResearchEvent(
                job_id=job_id,
                type="failed",
                message="研究任务失败：模型没有返回结果",
                payload={"round": round_index, "provider": provider.name},
            )
            holder["result"] = None
            return

        if result.input_tokens is not None:
            usage["input"] += result.input_tokens
        if result.output_tokens is not None:
            usage["output"] += result.output_tokens
        if result.estimated_cost_usd is not None:
            usage["cost"] += result.estimated_cost_usd
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
                "total_input_tokens": usage["input"],
                "total_output_tokens": usage["output"],
                "total_estimated_cost_usd": round(usage["cost"], 8),
            },
        )
        holder["result"] = result
        holder["streamed_report"] = streamed_report

    async def _visit_funnel(
        self,
        queue: list[dict[str, str]],
        target: int,
        visited: list[dict[str, str]],
        raw_by_url: dict[str, str],
        visited_urls: set[str],
        goal: str,
        job_id: str,
    ) -> AsyncIterator[ResearchEvent]:
        """按相关性滚动访问有限候选：全文达标早停，候选耗尽则降级退出。"""
        remaining = [source for source in queue if source["url"] not in visited_urls]
        while remaining and not should_stop_visiting(count_full_text(visited), target):
            needed_full_text = target - count_full_text(visited)
            batch = remaining[: max(1, needed_full_text)]
            remaining = remaining[len(batch):]
            urls = [source["url"] for source in batch]

            yield ResearchEvent(
                job_id=job_id,
                type="tool_start",
                message="调用工具：visit",
                payload={"tool": "visit", "arguments": {"url": urls, "goal": goal}},
            )
            visit_result = await self.tool_registry.call("visit", {"url": urls, "goal": goal})

            new_visited: list[dict[str, str]] = []
            for source in visit_result.sources:
                url = source.get("url", "")
                if not url or url in visited_urls:
                    continue
                visited_urls.add(url)
                enriched = dict(source)
                enriched["source_kind"] = "visited_source"
                enriched["citation_id"] = str(len(visited) + 1)
                visited.append(enriched)
                raw_by_url[url] = visit_result.source_texts.get(url, "")
                new_visited.append(enriched)

            yield ResearchEvent(
                job_id=job_id,
                type="tool_result",
                message="工具返回：visit",
                payload={
                    "tool": visit_result.name,
                    "content": visit_result.content,
                    "sources": self._source_snapshot(new_visited),
                    "all_sources": self._source_snapshot(visited),
                },
            )
            yield ResearchEvent(
                job_id=job_id,
                type="visit_progress",
                message="访问进度",
                payload={
                    "visited": len(visited),
                    "full_text": count_full_text(visited),
                    "target": target,
                    "full_text_target": target,
                    "remaining_candidates": len(remaining),
                },
            )

    @staticmethod
    def _extract_search_queries(content: str, fallback_query: str, count: int) -> list[str]:
        tool_call = AgentRuntime._extract_tool_call(content)
        queries: list[str] = []
        if isinstance(tool_call, dict) and tool_call.get("name") == "search":
            arguments = tool_call.get("arguments", {})
            if isinstance(arguments, dict):
                raw = arguments.get("query") or arguments.get("queries")
                if isinstance(raw, str):
                    queries = [raw]
                elif isinstance(raw, list):
                    queries = [item for item in raw if isinstance(item, str)]
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in queries:
            stripped = item.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                cleaned.append(stripped)
        if not cleaned:
            cleaned = [fallback_query.strip()[:120] or fallback_query]
        return cleaned[: max(1, count)]

    @staticmethod
    def _mark_search_candidates(
        sources: list[dict[str, str]],
        searched_urls: set[str],
    ) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        for source in sources:
            url = source.get("url", "")
            if not url or url in searched_urls:
                continue
            searched_urls.add(url)
            enriched = dict(source)
            enriched["source_kind"] = "search_result"
            enriched["search_id"] = AgentRuntime._roman_numeral(len(searched_urls))
            enriched.setdefault("read_status", "search_result")
            enriched.setdefault("evidence_level", "metadata")
            enriched.setdefault(
                "evidence_note",
                "Search result metadata. Visit this source before citing it in the final report.",
            )
            candidates.append(enriched)
        return candidates

    @staticmethod
    def _build_supplement_search_request(search_query_count: int) -> str:
        return (
            "以上是第一轮检索并访问后的证据要点。请审查证据缺口，输出补充检索。"
            f"使用 exactly {search_query_count} 个高命中英文搜索词，覆盖尚未被充分支持的方面。"
            "只输出一个 search 工具调用：\n"
            "<tool_call>\n{\"name\":\"search\",\"arguments\":{\"query\":[\"English search query\"]}}\n</tool_call>"
        )

    def _build_report_request(
        self,
        mode: str,
        selected_cards: list[EvidenceCard],
        selection: Any,
    ) -> str:
        policy = MODE_POLICIES.get(mode, MODE_POLICIES["deep"])
        cards_text = "\n\n".join(render_card(card) for card in selected_cards) or "（无可用证据卡片）"
        degrade_note = ""
        if selection.degraded or selection.full_text_shortfall:
            reasons = []
            if selection.full_text_shortfall:
                reasons.append(
                    f"全文证据只有 {selection.full_text_count} 条"
                    f"（最低质量线 {selection.minimum_full_text} 条）"
                )
            if selection.degraded:
                reasons.append(
                    f"可用来源只有 {selection.total_available} 条（目标 {selection.target} 条）"
                )
            degrade_note = (
                "注意：本次可用证据有限（" + "；".join(reasons) + "）。"
                "请在报告中明确区分哪些结论基于全文证据、哪些仅基于摘要/题录或访问受限来源，"
                "不要夸大证据强度，并在结尾说明证据局限。\n"
            )
        return (
            f"现在请基于以上证据卡片{REPORT_REQUEST_MARKER}。\n"
            f"研究模式：{mode}。{policy['report_guidance']}"
            f"正文必须为 {policy['min_report_chars']}-{policy['max_report_chars']} 字，"
            "字数不包含 References/参考文献列表与 [n] 引用标记。\n"
            "只能引用下面列出的来源，使用阿拉伯数字角标 [1]、[2]，禁止使用罗马编号或 [^1] 脚注，"
            "禁止引用未列出的来源，禁止编造数据。\n"
            f"{degrade_note}"
            "可引用来源（证据卡片）：\n"
            f"{cards_text}\n"
            "输出格式：用 <answer>...</answer> 包裹最终报告，正文使用 [n] 角标，最后一节命名为 ## References（APA 风格）。"
        )

    @staticmethod
    def _extract_tool_call(content: str) -> Optional[dict[str, Any]]:
        tool_calls = AgentRuntime._extract_tool_calls(content)
        return tool_calls[0] if tool_calls else None

    @staticmethod
    def _extract_tool_calls(content: str) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        for match in TOOL_CALL_PATTERN.finditer(content):
            parsed = AgentRuntime._parse_first_json_object(match.group(1).strip())
            if isinstance(parsed, dict):
                tool_calls.append(parsed)
        if tool_calls:
            return tool_calls

        start_match = TOOL_CALL_START_PATTERN.search(content)
        if not start_match:
            return []
        raw = content[start_match.end() :].strip()
        parsed = AgentRuntime._parse_first_json_object(raw)
        if not isinstance(parsed, dict):
            return []
        return [parsed]

    @staticmethod
    def _extract_answer(content: str) -> Optional[str]:
        match = ANSWER_PATTERN.search(content)
        if match:
            answer = match.group(1).strip()
            return answer or None
        start_match = ANSWER_START_PATTERN.search(content)
        if not start_match:
            return None
        answer = content[start_match.end() :].strip()
        return answer or None

    @staticmethod
    def _parse_first_json_object(raw: str) -> Optional[Any]:
        decoder = json.JSONDecoder()
        start = raw.find("{")
        if start < 0:
            return None
        try:
            parsed, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            return None
        return parsed

    @staticmethod
    def _missing_report_format(
        answer: str,
        sources: list[dict[str, str]],
        enabled: bool,
        *,
        min_body_chars: Optional[int] = None,
        max_body_chars: Optional[int] = None,
    ) -> list[str]:
        if not enabled:
            return []
        missing: list[str] = []
        if sources:
            citation_markers = re.findall(r"\[(\d+)\]", answer)
            if not citation_markers:
                missing.append("citation_markers")
            else:
                valid_citation_ids = {source.get("citation_id", "") for source in sources}
                if any(citation_id not in valid_citation_ids for citation_id in citation_markers):
                    missing.append("invalid_citation_markers")
        if re.search(r"\[\^\d+\]", answer):
            missing.append("footnote_citations")
        if not re.search(r"(^|\n)\s*(#{1,6}\s*)?(\*\*)?(References|参考文献)(\*\*)?\s*($|\n|[:：])", answer, re.IGNORECASE):
            missing.append("references_section")
        body_chars = AgentRuntime._count_report_body_chars(answer)
        if min_body_chars is not None and body_chars < min_body_chars:
            missing.append("report_too_short")
        if max_body_chars is not None and body_chars > max_body_chars:
            missing.append("report_too_long")
        return missing

    @staticmethod
    def _count_report_body_chars(answer: str) -> int:
        reference_heading = re.search(
            r"(^|\n)\s*(#{1,6}\s*)?(\*\*)?(References|参考文献)(\*\*)?\s*($|\n|[:：])",
            answer,
            re.IGNORECASE,
        )
        body = answer[: reference_heading.start()] if reference_heading else answer
        body = re.sub(r"\[\^\d+\]", "", body)
        body = re.sub(r"\[\d+(?:\s*[,，-]\s*\d+)*\]", "", body)
        body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
        body = re.sub(r"https?://\S+", "", body)
        body = re.sub(r"[#*_>`~|]", "", body)
        return sum(1 for character in body if character.isalnum())

    def _build_report_rewrite_request(
        self,
        missing_report_format: list[str],
        selected_cards: list[EvidenceCard],
        *,
        min_body_chars: int,
        max_body_chars: int,
        body_char_count: int,
    ) -> str:
        cards_text = "\n\n".join(render_card(card) for card in selected_cards) or "（无可用证据卡片）"
        missing_text = "、".join(missing_report_format)
        return (
            f"你刚才的最终报告格式不合格，缺少：{missing_text}。请重写 <answer>。\n"
            "硬性要求：\n"
            "1. 关键事实、数据、疗效、安全性和适用人群结论后必须使用 [1]、[2] 这种来源角标。\n"
            "   禁止使用 [^1]、[^2] 这种 Markdown 脚注格式。\n"
            "2. 最后一节必须命名为 References 或 参考文献。\n"
            "3. References 使用 APA 风格，尽量包含标题、来源和 URL。\n"
            "4. 如果来源标记为 blocked、metadata_only 或 metadata，只能说明它是题录/摘要/受限访问证据，不能写成已阅读全文。\n"
            "5. 只能引用下面列出的来源，不要编造来源。\n"
            f"6. 正文必须为 {min_body_chars}-{max_body_chars} 字，"
            f"不包含 References/参考文献列表与 [n] 引用标记；上一稿正文为 {body_char_count} 字。\n"
            f"{cards_text}"
        )

    @staticmethod
    def _visited_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
        return [source for source in sources if source.get("source_kind") == "visited_source" and source.get("citation_id")]

    @staticmethod
    def _renumber_selected_sources(
        sources: list[dict[str, str]],
        cards: list[EvidenceCard],
    ) -> tuple[list[dict[str, str]], list[EvidenceCard]]:
        cards_by_url = {card.url: card for card in cards}
        selected_sources: list[dict[str, str]] = []
        selected_cards: list[EvidenceCard] = []
        for index, source in enumerate(sources, start=1):
            citation_id = str(index)
            selected_source = dict(source)
            selected_source["citation_id"] = citation_id
            selected_sources.append(selected_source)
            card = cards_by_url.get(source.get("url", ""))
            if card is not None:
                selected_cards.append(replace(card, citation_id=citation_id))
        return selected_sources, selected_cards

    @staticmethod
    def _source_snapshot(sources: list[dict[str, str]]) -> list[dict[str, str]]:
        return [dict(source) for source in sources]

    @staticmethod
    def _roman_numeral(value: int) -> str:
        numerals = [
            (1000, "m"),
            (900, "cm"),
            (500, "d"),
            (400, "cd"),
            (100, "c"),
            (90, "xc"),
            (50, "l"),
            (40, "xl"),
            (10, "x"),
            (9, "ix"),
            (5, "v"),
            (4, "iv"),
            (1, "i"),
        ]
        remaining = max(1, value)
        parts: list[str] = []
        for number, numeral in numerals:
            while remaining >= number:
                parts.append(numeral)
                remaining -= number
        return "".join(parts)

    @staticmethod
    def _chunk_text(text: str, size: int = 180) -> list[str]:
        if not text:
            return []
        return [text[index : index + size] for index in range(0, len(text), size)]
