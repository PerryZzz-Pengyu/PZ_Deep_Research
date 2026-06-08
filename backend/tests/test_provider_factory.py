from __future__ import annotations

import pytest

from app.agent.providers.anthropic_provider import AnthropicProvider
from app.agent.providers.factory import ProviderFactory
from app.agent.providers.gemini_provider import GeminiProvider
from app.agent.providers.mock_provider import MockProvider
from app.agent.providers.openai_provider import OpenAIProvider
from app.config import Settings


def test_provider_factory_uses_default_provider_when_request_is_empty() -> None:
    provider = ProviderFactory(Settings(default_provider="mock")).create(None)

    assert isinstance(provider, MockProvider)


def test_provider_factory_passes_mock_delay() -> None:
    provider = ProviderFactory(Settings(mock_provider_delay_seconds=1.25)).create("mock")

    assert isinstance(provider, MockProvider)
    assert provider.delay_seconds == 1.25


def test_provider_factory_applies_default_model_to_real_providers() -> None:
    settings = Settings(
        default_model="shared-model",
        openai_api_key="openai-key",
        anthropic_api_key="anthropic-key",
        gemini_api_key="gemini-key",
    )
    factory = ProviderFactory(settings)

    assert isinstance(factory.create("openai"), OpenAIProvider)
    assert factory.create("openai").default_model == "shared-model"
    assert isinstance(factory.create("anthropic"), AnthropicProvider)
    assert factory.create("anthropic").default_model == "shared-model"
    assert isinstance(factory.create("gemini"), GeminiProvider)
    assert factory.create("gemini").default_model == "shared-model"


def test_provider_factory_provider_specific_model_wins() -> None:
    settings = Settings(
        default_model="shared-model",
        openai_api_key="openai-key",
        openai_model="openai-model",
        anthropic_api_key="anthropic-key",
        anthropic_model="claude-model",
        gemini_api_key="gemini-key",
        gemini_model="gemini-model",
    )
    factory = ProviderFactory(settings)

    assert factory.create("openai").default_model == "openai-model"
    assert factory.create("anthropic").default_model == "claude-model"
    assert factory.create("gemini").default_model == "gemini-model"


def test_provider_factory_rejects_unknown_provider() -> None:
    factory = ProviderFactory(Settings())

    with pytest.raises(ValueError):
        factory.create("qwen")
