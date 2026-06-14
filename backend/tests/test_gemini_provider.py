from __future__ import annotations

import asyncio
from types import SimpleNamespace

from google import genai

from app.agent.providers.gemini_provider import GeminiProvider
from app.agent.schemas import LLMMessage


def _fake_client_factory(response):
    captured: dict[str, object] = {}

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured.update(kwargs)
            return response

    class FakeAio:
        def __init__(self) -> None:
            self.models = FakeModels()
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"
            self.aio = FakeAio()

    return FakeClient, captured


def test_gemini_provider_records_usage_tokens(monkeypatch) -> None:
    response = SimpleNamespace(
        text="OK",
        usage_metadata=SimpleNamespace(prompt_token_count=7, candidates_token_count=2),
    )
    fake_client, captured = _fake_client_factory(response)
    monkeypatch.setattr(genai, "Client", fake_client)

    result = asyncio.run(
        GeminiProvider("test-key", "gemini-3.5-flash").generate(
            [LLMMessage(role="user", content="Reply with OK")],
            max_tokens=16,
        )
    )

    assert captured["model"] == "gemini-3.5-flash"
    assert result.content == "OK"
    assert result.input_tokens == 7
    assert result.output_tokens == 2


def test_gemini_provider_handles_missing_usage_metadata(monkeypatch) -> None:
    # Some responses (errors, certain models) omit usage_metadata; the ledger
    # must record None rather than crash.
    response = SimpleNamespace(text="OK", usage_metadata=None)
    fake_client, _ = _fake_client_factory(response)
    monkeypatch.setattr(genai, "Client", fake_client)

    result = asyncio.run(
        GeminiProvider("test-key", "gemini-3.5-flash").generate(
            [LLMMessage(role="user", content="Reply with OK")],
            max_tokens=16,
        )
    )

    assert result.content == "OK"
    assert result.input_tokens is None
    assert result.output_tokens is None
