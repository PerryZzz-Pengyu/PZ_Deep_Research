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

    def create(
        self,
        provider_name: Optional[str],
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> LLMProvider:
        # BYOK overrides (community edition); fall back to server-side settings.
        provider = (provider_name or self.settings.default_provider).lower()
        # Safety net: never pair a client-supplied base_url with the server API
        # key — that would exfiltrate the server key to an attacker-controlled
        # endpoint. The request layer already rejects this, but guard here too
        # since this is where the key and endpoint combine into an HTTP client.
        client_base_url = base_url if api_key else None
        if provider == "mock":
            return MockProvider(delay_seconds=self.settings.mock_provider_delay_seconds)
        if provider == "openai":
            return OpenAIProvider(
                api_key=api_key or self.settings.openai_api_key,
                base_url=client_base_url or self.settings.openai_base_url,
                default_model=self.settings.openai_model or self.settings.default_model,
            )
        if provider == "anthropic":
            return AnthropicProvider(
                api_key=api_key or self.settings.anthropic_api_key,
                default_model=self.settings.anthropic_model or self.settings.default_model,
            )
        if provider == "gemini":
            return GeminiProvider(
                api_key=api_key or self.settings.gemini_api_key,
                default_model=self.settings.gemini_model or self.settings.default_model,
            )
        raise ValueError(f"未知模型 Provider: {provider_name}")
