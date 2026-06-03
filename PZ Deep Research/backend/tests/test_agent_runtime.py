from __future__ import annotations

import asyncio
from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime
from app.agent.schemas import LLMMessage, LLMResult, ResearchRequest, ToolResult
from app.agent.tools import ToolRegistry, build_default_tool_registry
from app.agent.tools.base import AgentTool
from app.config import Settings


class StaticProvider(LLMProvider):
    name = "static"

    def __init__(self, result: LLMResult) -> None:
        self.result = result
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
        return self.result


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


class SequenceProvider(LLMProvider):
    name = "openai"

    def __init__(self, results: list[LLMResult]) -> None:
        self.results = results
        self.calls = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


class FixedTool(AgentTool):
    def __init__(self, name: str, result: ToolResult) -> None:
        self.name = name
        self.description = name
        self.result = result

    async def call(self, arguments: dict[str, object]) -> ToolResult:
        return self.result


class FixedProviderFactory:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def create(self, provider_name: Optional[str]) -> LLMProvider:
        return self.provider


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
        provider = StaticProvider(
            LLMResult(
                content="<answer>\n带用量统计的最终报告\n</answer>",
                model="unit-test-model",
                input_tokens=120,
                output_tokens=30,
                estimated_cost_usd=0.00045,
            )
        )
        runtime = AgentRuntime(
            provider_factory=FixedProviderFactory(provider),
            tool_registry=ToolRegistry([]),
        )
        request = ResearchRequest(query="测试 LLM 用量统计", mode="quick", provider="mock")
        return [event async for event in runtime.run("usage-job", request)]

    events = asyncio.run(run_runtime())
    usage_events = [event for event in events if event.type == "llm_result"]

    assert len(usage_events) == 1
    assert usage_events[0].payload["model"] == "unit-test-model"
    assert usage_events[0].payload["input_tokens"] == 120
    assert usage_events[0].payload["output_tokens"] == 30
    assert usage_events[0].payload["total_input_tokens"] == 120
    assert usage_events[0].payload["total_output_tokens"] == 30
    assert usage_events[0].payload["estimated_cost_usd"] == 0.00045


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

    assert calls == 2
    assert "llm_retry" in event_types
    assert events[-1].type == "completed"
    assert events[-1].payload["final_report"] == "重试后成功"


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


def test_real_provider_must_collect_evidence_before_answering() -> None:
    async def run_runtime():
        provider = SequenceProvider(
            [
                LLMResult(content="<answer>\n过早报告\n</answer>", model="openai-test"),
                LLMResult(
                    content='<tool_call>\n{"name":"search","arguments":{"query":["GLP-1 obesity trial"]}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(
                    content='<tool_call>\n{"name":"visit","arguments":{"url":["https://example.com/paper"],"goal":"读取证据"}}\n</tool_call>',
                    model="openai-test",
                ),
                LLMResult(content="<answer>\n最终报告引用来源 [1]\n</answer>", model="openai-test"),
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
                            sources=[
                                {
                                    "title": "GLP-1 Trial",
                                    "url": "https://example.com/paper",
                                    "snippet": "trial evidence",
                                }
                            ],
                        ),
                    ),
                    FixedTool(
                        "visit",
                        ToolResult(name="visit", content="网页正文", sources=[]),
                    ),
                ]
            ),
        )
        request = ResearchRequest(query="GLP-1 for obesity", mode="deep", provider="openai")
        return [event async for event in runtime.run("evidence-job", request)]

    events = asyncio.run(run_runtime())
    event_types = [event.type for event in events]
    tool_names = [event.payload["tool"] for event in events if event.type == "tool_start"]
    completed = events[-1]

    assert "evidence_required" in event_types
    assert tool_names == ["search", "visit"]
    assert "report_delta" in event_types
    assert completed.type == "completed"
    assert completed.payload["final_report"] == "最终报告引用来源 [1]"
    assert completed.payload["sources"][0]["citation_id"] == "1"
