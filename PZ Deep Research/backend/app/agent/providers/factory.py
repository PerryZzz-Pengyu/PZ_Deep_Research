from __future__ import annotations

from typing import Optional

from app.agent.providers.anthropic_provider import AnthropicProvider
from app.agent.providers.base import LLMProvider
from app.agent.providers.gemini_provider import GeminiProvider
from app.agent.providers.mock_provider import MockProvider
from app.agent.providers.openai_provider import OpenAIProvider
from app.config import Settings


class ProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, provider_name: Optional[str]) -> LLMProvider:
        provider = (provider_name or self.settings.default_provider).lower()
        if provider == "mock":
            return MockProvider()
        if provider == "openai":
            return OpenAIProvider(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                default_model=self.settings.openai_model or self.settings.default_model,
            )
        if provider == "anthropic":
            return AnthropicProvider(
                api_key=self.settings.anthropic_api_key,
                default_model=self.settings.anthropic_model or self.settings.default_model,
            )
        if provider == "gemini":
            return GeminiProvider(
                api_key=self.settings.gemini_api_key,
                default_model=self.settings.gemini_model or self.settings.default_model,
            )
        raise ValueError(f"未知模型 Provider: {provider_name}")
