from __future__ import annotations

import asyncio
from types import SimpleNamespace

import anthropic

from app.agent.providers.anthropic_provider import AnthropicProvider
from app.agent.schemas import LLMMessage


def test_anthropic_provider_omits_empty_system_field(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="OK")],
                usage=SimpleNamespace(input_tokens=3, output_tokens=1),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)

    result = asyncio.run(
        AnthropicProvider("test-key", "claude-sonnet-4-6").generate(
            [LLMMessage(role="user", content="Reply with OK")],
            max_tokens=16,
        )
    )

    assert "system" not in captured
    assert captured["model"] == "claude-sonnet-4-6"
    assert result.content == "OK"
    assert result.input_tokens == 3
    assert result.output_tokens == 1


def test_anthropic_provider_sends_joined_system_messages(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="OK")],
                usage=SimpleNamespace(input_tokens=5, output_tokens=1),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)

    asyncio.run(
        AnthropicProvider("test-key", "claude-sonnet-4-6").generate(
            [
                LLMMessage(role="system", content="Follow citations."),
                LLMMessage(role="system", content="Be concise."),
                LLMMessage(role="user", content="Reply with OK"),
            ],
            max_tokens=16,
        )
    )

    assert captured["system"] == "Follow citations.\n\nBe concise."
