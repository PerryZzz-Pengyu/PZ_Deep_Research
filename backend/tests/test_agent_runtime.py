from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime, MODE_POLICIES
from app.agent.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_ZH_FOR_REVIEW, build_user_prompt
from app.agent.schemas import LLMMessage, LLMResult, LLMStreamEvent, ResearchRequest, ToolResult
from app.agent.tools import ToolRegistry, build_default_tool_registry
from app.agent.tools.base import AgentTool
from app.config import Settings


class FlakyProvider(LLMProvider):
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return LLMResult(content="<answer>\n重试后成功\n</answer>", model="flaky-model")


class SlowProvider(LLMProvider):
    name = "slow"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        await asyncio.sleep(0.2)
        return LLMResult(content="<answer>\n不应该返回\n</answer>", model="slow-model")


class StreamingProvider(LLMProvider):
    name = "streaming"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        return LLMResult(content="<answer>\n不应该使用非流式\n</answer>", model="stream-model")

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMStreamEvent]:
        yield LLMStreamEvent(type="delta", delta="<answer>\n")
        yield LLMStreamEvent(type="delta", delta="流式报告 [1]\n## References\nGLP-1 Trial. (n.d.). https://example.com/paper")
        yield LLMStreamEvent(
            type="done",
            result=LLMResult(
                content="<answer>\n流式报告 [1]\n## References\nGLP-1 Trial. (n.d.). https://example.com/paper\n</answer>",
                model="stream-model",
            ),
        )


class SequenceProvider(LLMProvider):
    name = "openai"

    def __init__(self, results: list[LLMResult | Exception]) -> None:
        self.results = results
        self.calls = 0
        self.message_history: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        self.message_history.append(list(messages))
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


class FixedTool(AgentTool):
    def __init__(self, name: str, result: ToolResult) -> None:
        self.name = name
        self.description = name
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def call(self, arguments: dict[str, object]) -> ToolResult:
        self.calls.append(arguments)
        return self.result


class SequenceTool(AgentTool):
    def __init__(self, name: str, results: list[ToolResult]) -> None:
        self.name = name
        self.description = name
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def call(self, arguments: dict[str, object]) -> ToolResult:
        self.calls.append(arguments)
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


class EchoVisitTool(AgentTool):
    """按被请求的 URL 回显成已访问来源，用于验证 Runtime 驱动的访问漏斗（FixedTool 忽略入参，无法测计数）。"""

    name = "visit"
    description = "visit"

    def __init__(
        self,
        *,
        evidence_level: str = "full_text",
        read_status: str = "full_text",
        text: str = "full text evidence " * 100,
    ) -> None:
        self.evidence_level = evidence_level
        self.read_status = read_status
        self.text = text
        self.calls: list[dict[str, object]] = []

    async def call(self, arguments: dict[str, object]) -> ToolResult:
        self.calls.append(arguments)
        urls = arguments.get("url") or []
        if isinstance(urls, str):
            urls = [urls]
        sources = [
            {
                "title": f"Visited {url}",
                "url": str(url),
                "snippet": "evidence",
                "read_status": self.read_status,
                "evidence_level": self.evidence_level,
                "evidence_note": "note",
                "content_preview": "preview",
            }
            for url in urls
        ]
        texts = {str(url): self.text for url in urls}
        return ToolResult(name="visit", content="网页正文", sources=sources, source_texts=texts)


class MixedEvidenceVisitTool(EchoVisitTool):
    async def call(self, arguments: dict[str, object]) -> ToolResult:
        self.calls.append(arguments)
        urls = arguments.get("url") or []
        if isinstance(urls, str):
            urls = [urls]
        sources = []
        texts = {}
        for url in urls:
            index = int(str(url).rsplit("-", 1)[-1])
            full_text = index > 3
            sources.append(
                {
                    "title": f"Visited {url}",
                    "url": str(url),
                    "snippet": "evidence",
                    "read_status": "full_text" if full_text else "metadata_only",
                    "evidence_level": "full_text" if full_text else "metadata_only",
                    "evidence_note": "note",
                    "content_preview": "preview",
                }
            )
            texts[str(url)] = "short evidence"
        return ToolResult(name="visit", content="网页正文", sources=sources, source_texts=texts)


class FixedProviderFactory:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def create(self, provider_name: Optional[str]) -> LLMProvider:
        return self.provider


def make_sources(count: int, *, start: int = 1) -> list[dict[str, str]]:
    return [
        {
            "title": f"GLP-1 Evidence Source {index}",
            "url": f"https://example.com/paper-{index}",
            "snippet": "trial evidence",
        }
        for index in range(start, start + count)
    ]


def make_visit_sources(count: int, *, start: int = 1) -> list[dict[str, str]]:
    return [
        {
            **source,
            "read_status": "full_text",
            "evidence_level": "full_text",
            "evidence_note": "测试全文证据。",
            "content_preview": "full text evidence",
        }
        for source in make_sources(count, start=start)
    ]


def make_valid_answer(message: str, mode: str, citations: str = "[1]") -> str:
    minimum = int(MODE_POLICIES[mode]["min_report_chars"])
    body = f"{message} {citations}\n\n" + ("研" * minimum)
    return (
        "<answer>\n"
        f"{body}\n\n"
        "## References\n"
        "Source. (n.d.). Evidence source. https://example.com/paper-1\n"
        "</answer>"
    )


def test_mode_policies_match_product_spec() -> None:
    assert MODE_POLICIES["quick"]["search_query_count"] == 1
    assert MODE_POLICIES["quick"]["visit_source_count"] == 3
    assert MODE_POLICIES["quick"]["full_text_source_count"] == 1
    assert MODE_POLICIES["quick"]["min_report_chars"] == 400
    assert MODE_POLICIES["quick"]["max_report_chars"] == 500

    assert MODE_POLICIES["deep"]["search_query_count"] == 3
    assert MODE_POLICIES["deep"]["visit_source_count"] == 10
    assert MODE_POLICIES["deep"]["full_text_source_count"] == 3
    assert MODE_POLICIES["deep"]["min_report_chars"] == 1300
    assert MODE_POLICIES["deep"]["max_report_chars"] == 1500

    assert MODE_POLICIES["expert"]["search_query_count"] == 5
    assert MODE_POLICIES["expert"]["visit_source_count"] == 20
    assert MODE_POLICIES["expert"]["full_text_source_count"] == 5
    assert MODE_POLICIES["expert"]["min_report_chars"] == 3000
    assert MODE_POLICIES["expert"]["max_report_chars"] == 3500
    assert MODE_POLICIES["expert"]["first_visit_source_count"] == 10
    assert MODE_POLICIES["expert"]["search_rounds"] == 2


def test_prompt_files_are_bilingual_and_mode_aligned() -> None:
    assert "English production prompt" in SYSTEM_PROMPT
    assert "中文对照提示词" in SYSTEM_PROMPT_ZH_FOR_REVIEW
    for text in [SYSTEM_PROMPT, SYSTEM_PROMPT_ZH_FOR_REVIEW]:
        assert "search -> visit -> answer" in text or "搜索 -> 访问 -> 报告" in text
        assert "quick" in text or "快速" in text
        assert "deep" in text or "深度" in text
        assert "expert" in text or "专家" in text
    user_prompt = build_user_prompt("GLP-1", "quick")
    assert "Selected research mode: quick" in user_prompt
    assert "search -> visit -> answer" in user_prompt


def test_report_format_accepts_bold_references_heading() -> None:
    answer = "最终报告引用来源 [1]\n\n**References**\nSource. (n.d.). https://example.com/paper-1"
    sources = [{**make_visit_sources(1)[0], "citation_id": "1", "source_kind": "visited_source"}]

    missing = AgentRuntime._missing_report_format(answer, sources, enabled=True)

    assert missing == []


def test_report_body_length_excludes_references_and_citation_markers() -> None:
    answer = f"{'研' * 400} [1]\n\n## References\n{'参考文献内容' * 100}"

    assert AgentRuntime._count_report_body_chars(answer) == 400
    assert AgentRuntime._missing_report_format(
        answer,
        [],
        enabled=True,
        min_body_chars=400,
        max_body_chars=500,
    ) == []


def test_report_body_length_rejects_out_of_range_content() -> None:
    too_short = f"{'研' * 399}\n\n## References\nSource"
    too_long = f"{'研' * 501}\n\n## References\nSource"

    assert "report_too_short" in AgentRuntime._missing_report_format(
        too_short,
        [],
        enabled=True,
        min_body_chars=400,
        max_body_chars=500,
    )
    assert "report_too_long" in AgentRuntime._missing_report_format(
        too_long,
        [],
        enabled=True,
        min_body_chars=400,
        max_body_chars=500,
    )


def test_mock_runtime_completes_research_flow() -> None:
    async def run_runtime():
        settings = Settings(default_provider="mock")
        runtime = AgentRuntime(
            provider_factory=ProviderFactory(settings),
            tool_registry=build_default_tool_registry(settings),
        )
        request = ResearchRequest(
            query="测试 mock Agent Runtime",
            mode="quick",
            provider="mock",
        )
        return [event async for event in runtime.run("test-job", request)]

    events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]

    assert "status" in event_types
    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert event_types[-1] == "completed"
    assert "final_report" in events[-1].payload
    assert "Agent Runtime" in str(events[-1].payload["final_report"])


def test_runtime_emits_search_and_visit_tool_events() -> None:
    async def run_runtime():
        settings = Settings(default_provider="mock")
        runtime = AgentRuntime(
            provider_factory=ProviderFactory(settings),
            tool_registry=build_default_tool_registry(settings),
        )
        request = ResearchRequest(
            query="测试工具调用顺序",
            mode="quick",
            provider="mock",
        )
        return [event async for event in runtime.run("test-job", request)]

    events = asyncio.run(run_runtime())
    tool_names = [
        event.payload["tool"]
        for event in events
        if event.type == "tool_start"
    ]

    assert tool_names == ["search", "visit"]


def test_runtime_emits_llm_usage_event() -> None:
    async def run_runtime():
        # 新流程：先 search 轮，后报告轮；用量应跨轮累加。
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["q"]}}\n</tool_call>',
                    model="unit-test-model",
                    input_tokens=120,
                    output_tokens=30,
                    estimated_cost_usd=0.00045,
                ),
                LLMResult(
                    content=make_valid_answer("带用量统计的最终报告", "quick"),
                    model="unit-test-model",
                    input_tokens=200,
                    output_tokens=50,
                    estimated_cost_usd=0.00055,
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([]),
        )
        request = ResearchRequest(query="测试 LLM 用量统计", mode="quick", provider="mock")
        return [event async for event in runtime.run("usage-job", request)]

    events = asyncio.run(run_runtime())
    usage_events = [event for event in events if event.type == "llm_result"]

    assert len(usage_events) == 2
    assert usage_events[0].payload["model"] == "unit-test-model"
    assert usage_events[0].payload["input_tokens"] == 120
    # 跨轮累加
    assert usage_events[-1].payload["total_input_tokens"] == 320
    assert usage_events[-1].payload["total_output_tokens"] == 80
    assert round(usage_events[-1].payload["total_estimated_cost_usd"], 5) == 0.001


def test_runtime_emits_llm_delta_events_for_streaming_provider() -> None:
    async def run_runtime():
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(StreamingProvider()),
            tool_registry=ToolRegistry([]),
        )
        request = ResearchRequest(query="测试 LLM 流式输出", mode="quick", provider="mock")
        return [event async for event in runtime.run("stream-job", request)]

    events = asyncio.run(run_runtime())
    delta_events = [event for event in events if event.type == "llm_delta"]
    event_types = [event.type for event in events]

    # 报告轮会把 <answer> 内容作为 report_delta 实时推送
    assert delta_events
    assert "report_delta" in event_types
    # report_delta 出现在最后一次 llm_result（报告轮返回）之前
    last_report_delta = max(i for i, t in enumerate(event_types) if t == "report_delta")
    last_llm_result = max(i for i, t in enumerate(event_types) if t == "llm_result")
    assert last_report_delta < last_llm_result
    assert events[-1].type == "completed"


def test_runtime_recovers_complete_json_from_unclosed_tool_call() -> None:
    content = '<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper"],"goal":"读取证据"}}'

    tool_call = AgentRuntime._extract_tool_call(content)

    assert tool_call == {
        "name": "visit",
        "arguments": {"url": ["https://example.com/paper"], "goal": "读取证据"},
    }


def test_runtime_recovers_unclosed_answer_body() -> None:
    content = "<answer>\n最终报告 [1]\n\n## References\nSource. (n.d.). https://example.com"

    answer = AgentRuntime._extract_answer(content)

    assert answer == "最终报告 [1]\n\n## References\nSource. (n.d.). https://example.com"


def test_runtime_retries_provider_failure_before_succeeding() -> None:
    async def run_runtime():
        provider = FlakyProvider()
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([]),
            max_llm_retries=1,
            llm_timeout_seconds=1,
        )
        request = ResearchRequest(query="测试 LLM 重试", mode="quick", provider="mock")
        events = [event async for event in runtime.run("retry-job", request)]
        return provider.calls, events

    calls, events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]

    # 第一次调用失败后重试成功；新流程下后续还有报告轮，故总调用数 >= 2
    assert calls >= 2
    assert "llm_retry" in event_types
    assert events[-1].type == "completed"
    assert events[-1].payload["final_report"] == "重试后成功"


def test_report_transient_failure_retries_from_selected_evidence() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content=(
                        '<tool_call>\n{"name":"search","arguments":{"query":'
                        '["agent architecture survey"]}}\n</tool_call>'
                    ),
                    model="openai-test",
                ),
                RuntimeError("503 UNAVAILABLE: high demand"),
                LLMResult(
                    content=make_valid_answer("重试后报告", "quick"),
                    model="openai-test",
                ),
            ]
        )
        search_tool = FixedTool(
            "search",
            ToolResult(name="search", content="搜索结果", sources=make_sources(3)),
        )
        visit_tool = FixedTool(
            "visit",
            ToolResult(name="visit", content="网页正文", sources=make_visit_sources(3)),
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([search_tool, visit_tool]),
            max_llm_retries=3,
            llm_retry_base_delay_seconds=0,
        )
        request = ResearchRequest(
            query="Agent 架构",
            mode="quick",
            provider="openai",
        )
        events = [event async for event in runtime.run("report-retry-job", request)]
        return search_tool, visit_tool, events

    search_tool, visit_tool, events = asyncio.run(run_runtime())
    retry_events = [event for event in events if event.type == "llm_retry"]

    assert len(search_tool.calls) == 1
    assert len(visit_tool.calls) == 1
    assert len(retry_events) == 1
    assert retry_events[0].payload["stage"] == "report"
    assert retry_events[0].payload["resume_from"] == "selected_evidence"
    assert "仅重试报告生成" in retry_events[0].message
    assert events[-1].type == "completed"


def test_non_transient_provider_error_does_not_retry() -> None:
    async def run_runtime():
        provider = SequenceProvider([RuntimeError("400 invalid model configuration")])
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([]),
            max_llm_retries=3,
        )
        request = ResearchRequest(query="错误配置", mode="quick", provider="openai")
        events = [event async for event in runtime.run("non-transient-job", request)]
        return provider, events

    provider, events = asyncio.run(run_runtime())

    assert provider.calls == 1
    assert not any(event.type == "llm_retry" for event in events)
    assert events[-1].type == "failed"
    assert events[-1].payload["transient"] is False


def test_provider_specific_evidence_models_use_cheapest_configured_model() -> None:
    runtime = AgentRuntime(
        provider_factory=FixedProviderFactory(SequenceProvider([])),
        tool_registry=ToolRegistry([]),
        evidence_extraction_model="gpt-5-nano",
        evidence_extraction_models={
            "openai": "gpt-5-nano",
            "anthropic": "claude-haiku-4-5-20251001",
            "gemini": "gemini-2.5-flash-lite",
        },
    )

    assert runtime._evidence_model_for_provider("openai", "gpt-5.5") == "gpt-5-nano"
    assert (
        runtime._evidence_model_for_provider("anthropic", "claude-sonnet-4-6")
        == "claude-haiku-4-5-20251001"
    )
    assert (
        runtime._evidence_model_for_provider("gemini", "gemini-3.5-flash")
        == "gemini-2.5-flash-lite"
    )


def test_runtime_timeout_emits_failed_event() -> None:
    async def run_runtime():
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(SlowProvider()),
            tool_registry=ToolRegistry([]),
            max_llm_retries=0,
            llm_timeout_seconds=0.01,
        )
        request = ResearchRequest(query="测试 LLM 超时", mode="quick", provider="mock")
        return [event async for event in runtime.run("timeout-job", request)]

    events = asyncio.run(run_runtime())

    assert events[-1].type == "failed"
    assert "超时" in events[-1].message
    assert events[-1].payload["round"] == 1


def test_real_provider_runtime_drives_search_then_visit_before_report() -> None:
    async def run_runtime():
        # 新流程：模型只输出 search，Runtime 自动访问候选并喂证据卡片，模型最后写报告。
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("最终报告引用来源", "deep"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(10))),
                    EchoVisitTool(),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        return [event async for event in runtime.run("evidence-job", request)]

    events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]
    completed = events[-1]

    assert tool_names[0] == "search"
    assert "visit" in tool_names
    assert "source_selected" in event_types
    assert "report_delta" in event_types
    assert completed.type == "completed"
    assert "最终报告引用来源 [1]" in completed.payload["final_report"]
    assert completed.payload["sources"][0]["citation_id"] == "1"


def test_real_provider_quick_mode_visits_before_report() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("快速模式访问后的最终报告", "quick"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(3))),
                    EchoVisitTool(),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        return [event async for event in runtime.run("quick-evidence-job", request)]

    events = asyncio.run(run_runtime())
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]

    assert tool_names[0] == "search"
    assert "visit" in tool_names
    assert events[-1].type == "completed"
    assert "快速模式访问后的最终报告" in events[-1].payload["final_report"]


def test_quick_mode_trims_search_queries_to_policy() -> None:
    async def run_runtime():
        # quick 模式只允许 1 个搜索词，模型多给的应被裁剪。
        provider = SequenceProvider(
            [
                LLMResult(
                    content=(
                        '<tool_call>\n{"name":"search","arguments":{"query":['
                        '"GLP-1 non-diabetic obesity randomized trial",'
                        '"extra query should be ignored"'
                        ']}}\n</tool_call>'
                    ),
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("快速 essay 报告", "quick"),
                    model="openai-test",
                ),
            ]
        )
        search_tool = FixedTool(
            "search",
            ToolResult(name="search", content="搜索结果", sources=make_sources(4)),
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([search_tool, EchoVisitTool()]),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        events = [event async for event in runtime.run("quick-policy-job", request)]
        return events, search_tool.calls

    events, search_calls = asyncio.run(run_runtime())

    # 搜索词裁剪到模式上限 1 个
    assert search_calls[0]["query"] == ["GLP-1 non-diabetic obesity randomized trial"]
    assert events[-1].type == "completed"


def test_search_candidates_use_roman_ids_and_visited_sources_use_citation_ids() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content='<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper-1","https://example.com/paper-2","https://example.com/paper-3"],"goal":"读取证据"}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("最终报告只引用访问来源", "quick", "[1][2][3]"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(4))),
                    FixedTool("visit", ToolResult(name="visit", content="网页正文", sources=make_visit_sources(3))),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        return [event async for event in runtime.run("source-id-job", request)]

    events = asyncio.run(run_runtime())
    tool_results = [event for event in events if event.type == "tool_result"]
    search_sources = tool_results[0].payload["sources"]
    visit_sources = tool_results[1].payload["sources"]
    completed_sources = events[-1].payload["sources"]

    assert search_sources[0]["search_id"] == "i"
    assert search_sources[1]["search_id"] == "ii"
    assert "citation_id" not in search_sources[0]
    assert search_sources[0]["read_status"] == "search_result"
    assert search_sources[0]["source_kind"] == "search_result"

    assert [source["citation_id"] for source in visit_sources] == ["1", "2", "3"]
    assert all(source["source_kind"] == "visited_source" for source in visit_sources)
    assert len(completed_sources) == 3
    assert [source["citation_id"] for source in completed_sources] == ["1", "2", "3"]


def test_report_cannot_cite_unvisited_search_candidates() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content='<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper-1","https://example.com/paper-2","https://example.com/paper-3"],"goal":"读取证据"}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content="<answer>\n错误引用未访问来源 [4]\n\n## References\nSource. (n.d.). https://example.com/paper-4\n</answer>",
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("修正后只引用访问来源", "quick"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(4))),
                    FixedTool("visit", ToolResult(name="visit", content="网页正文", sources=make_visit_sources(3))),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        return [event async for event in runtime.run("invalid-citation-job", request)]

    events = asyncio.run(run_runtime())
    citation_events = [event for event in events if event.type == "citation_required"]

    assert citation_events
    assert "invalid_citation_markers" in citation_events[0].payload["missing"]
    assert events[-1].type == "completed"
    assert "修正后只引用访问来源" in events[-1].payload["final_report"]


def test_quick_mode_degrades_when_no_full_text_evidence() -> None:
    async def run_runtime():
        # 候选全是受限来源（无全文）：漏斗访问完所有候选后不卡死，选源标记 full_text 不足并照常出报告。
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("证据受限下的报告", "quick"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(3))),
                    EchoVisitTool(evidence_level="metadata_only", read_status="metadata_only"),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        return [event async for event in runtime.run("full-text-job", request)]

    events = asyncio.run(run_runtime())
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]
    selected_events = [event for event in events if event.type == "source_selected"]

    assert tool_names[0] == "search"
    assert "visit" in tool_names
    assert selected_events
    # 没有全文证据但来源数够：full_text 不足、未降级数量，照常出报告（不卡死）
    assert selected_events[0].payload["full_text_count"] == 0
    assert selected_events[0].payload["full_text_shortfall"] is True
    assert events[-1].type == "completed"


def test_deep_mode_exhausts_finite_candidates_then_selects_ten_when_full_text_is_unavailable() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["q1","q2","q3"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(content=make_valid_answer("深度模式报告", "deep"), model="openai-test"),
            ]
        )
        visit_tool = EchoVisitTool(
            evidence_level="metadata_only",
            read_status="metadata_only",
            text="short abstract",
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(15))),
                    visit_tool,
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        events = [event async for event in runtime.run("bounded-visit-job", request)]
        return events, visit_tool.calls

    events, visit_calls = asyncio.run(run_runtime())
    selected_event = next(event for event in events if event.type == "source_selected")
    visited_urls = [
        url
        for call in visit_calls
        for url in call.get("url", [])
        if isinstance(url, str)
    ]

    assert len(visited_urls) == 15
    assert selected_event.payload["full_text_count"] == 0
    assert selected_event.payload["full_text_shortfall"] is True
    assert selected_event.payload["selected_count"] == 10
    assert len(events[-1].payload["sources"]) == 10


def test_final_selected_sources_are_quality_first_and_renumbered_contiguously() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["q"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("最终来源连续编号", "quick", "[1][2][3]"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(6))),
                    MixedEvidenceVisitTool(),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="quick", provider="openai")
        return [event async for event in runtime.run("renumber-job", request)]

    events = asyncio.run(run_runtime())
    selected = next(event for event in events if event.type == "source_selected").payload["sources"]

    assert [source["url"] for source in selected] == [
        "https://example.com/paper-4",
        "https://example.com/paper-5",
        "https://example.com/paper-6",
    ]
    assert [source["citation_id"] for source in selected] == ["1", "2", "3"]
    assert events[-1].payload["sources"] == selected


def test_real_provider_always_searches_before_visit() -> None:
    async def run_runtime():
        # 即使模型先抛出 visit，Runtime 也只认 search；访问由 Runtime 在 search 之后驱动。
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper"],"goal":"过早访问"}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("按顺序完成后的报告", "deep"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool("search", ToolResult(name="search", content="搜索结果", sources=make_sources(10))),
                    EchoVisitTool(),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        return [event async for event in runtime.run("order-job", request)]

    events = asyncio.run(run_runtime())
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]

    assert tool_names[0] == "search"
    assert tool_names.index("search") < tool_names.index("visit")
    assert events[-1].type == "completed"


def test_expert_mode_runs_two_search_stages() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["q1","q2","q3","q4","q5"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["gap1","gap2","gap3","gap4","gap5"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("专家最终报告", "expert", "[1][11]"),
                    model="openai-test",
                ),
            ]
        )
        search_tool = SequenceTool(
            "search",
            [
                ToolResult(name="search", content="第一轮搜索", sources=make_sources(20)),
                ToolResult(name="search", content="第二轮搜索", sources=make_sources(20, start=21)),
            ],
        )
        visit_tool = EchoVisitTool(text="short evidence")
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([search_tool, visit_tool]),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="expert", provider="openai")
        events = [event async for event in runtime.run("expert-policy-job", request)]
        return events, search_tool.calls, visit_tool.calls

    events, search_calls, visit_calls = asyncio.run(run_runtime())
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]

    # 专家模式跑两轮 search，每轮后由 Runtime 驱动 visit
    assert tool_names == ["search", "visit", "search", "visit"]
    assert len(search_calls) == 2
    assert len(visit_calls) == 2
    assert [len(call["url"]) for call in visit_calls] == [10, 10]
    assert len(events[-1].payload["sources"]) == 20
    assert events[-1].type == "completed"


def test_real_provider_prefers_tool_call_when_answer_and_tool_call_are_mixed() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content=(
                        '<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper"],"goal":"读取证据"}}\n</tool_call>'
                        "\n<answer>\n这段早答应该被忽略 [1]\n</answer>"
                    ),
                    model="openai-test",
                ),
                LLMResult(
                    content=make_valid_answer("工具优先后的最终报告", "deep"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool(
                        "search",
                        ToolResult(
                            name="search",
                            content="搜索结果",
                            sources=make_sources(10),
                        ),
                    ),
                    FixedTool("visit", ToolResult(name="visit", content="网页正文", sources=make_visit_sources(10))),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        return [event async for event in runtime.run("mixed-job", request)]

    events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]

    assert tool_names == ["search", "visit"]
    assert "evidence_required" not in event_types
    assert events[-1].type == "completed"
    assert "工具优先后的最终报告" in events[-1].payload["final_report"]


def test_real_provider_must_rewrite_report_with_references() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content='<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper"],"goal":"读取证据"}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(content="<answer>\n有引用但没有参考文献 [1]\n</answer>", model="openai-test"),
                LLMResult(
                    content=make_valid_answer("重写后报告", "deep"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool(
                        "search",
                        ToolResult(
                            name="search",
                            content="搜索结果",
                            sources=make_sources(10),
                        ),
                    ),
                    FixedTool("visit", ToolResult(name="visit", content="网页正文", sources=make_visit_sources(10))),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        return [event async for event in runtime.run("citation-job", request)]

    events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]

    assert "citation_required" in event_types
    assert events[-1].type == "completed"
    assert "## References" in events[-1].payload["final_report"]


def test_report_rewrite_uses_bounded_fresh_context() -> None:
    async def run_runtime():
        too_long_answer = (
            "<answer>\n"
            + ("研" * 1600)
            + " [1]\n\n## References\n"
            + "Source. (n.d.). Evidence source. https://example.com/paper-1\n"
            + "</answer>"
        )
        provider = SequenceProvider(
            [
                LLMResult(
                    content=(
                        '<tool_call>\n{"name":"search","arguments":{"query":'
                        '["agent architecture survey","LLM agent workflow","multi-agent systems"]}}\n'
                        "</tool_call>"
                    ),
                    model="openai-test",
                ),
                LLMResult(content=too_long_answer, model="openai-test"),
                LLMResult(
                    content=make_valid_answer("压缩后的报告", "deep"),
                    model="openai-test",
                ),
            ]
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry(
                [
                    FixedTool(
                        "search",
                        ToolResult(name="search", content="搜索结果", sources=make_sources(10)),
                    ),
                    FixedTool(
                        "visit",
                        ToolResult(
                            name="visit",
                            content="网页正文",
                            sources=make_visit_sources(10),
                        ),
                    ),
                ]
            ),
        )
        request = ResearchRequest(
            query="各种架构 Agent 的运行原理",
            mode="deep",
            provider="openai",
        )
        events = [event async for event in runtime.run("bounded-report-context", request)]
        return provider, events

    provider, events = asyncio.run(run_runtime())

    assert events[-1].type == "completed"
    assert len(provider.message_history) == 3

    initial_report_messages = provider.message_history[1]
    rewrite_messages = provider.message_history[2]
    assert len(initial_report_messages) == 2
    assert len(rewrite_messages) == 2
    assert all("<tool_response>" not in message.content for message in initial_report_messages)
    assert all("<tool_response>" not in message.content for message in rewrite_messages)
    assert "<previous_report>" in rewrite_messages[1].content
    assert "压缩到约 1400 字" in rewrite_messages[1].content
    assert "保留上一稿约 88% 的正文" in rewrite_messages[1].content
    assert "必须至少删除 200 个计数字符" in rewrite_messages[1].content
    assert "可引用来源（证据卡片）" not in rewrite_messages[1].content
    assert "full text evidence" not in rewrite_messages[1].content
    assert rewrite_messages[1].content.count("<previous_report>") == 1
