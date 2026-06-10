from __future__ import annotations

from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.schemas import LLMMessage, LLMResult


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, default_model: str = "") -> None:
        self.api_key = api_key
        self.default_model = default_model

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置")

        from anthropic import AsyncAnthropic

        selected_model = model or self.default_model
        if not selected_model:
            raise RuntimeError("ANTHROPIC_MODEL 未配置")

        system_parts = [message.content for message in messages if message.role == "system"]
        chat_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        ]
        request_kwargs = {
            "model": selected_model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            request_kwargs["system"] = "\n\n".join(system_parts)

        async with AsyncAnthropic(api_key=self.api_key) as client:
            response = await client.messages.create(**request_kwargs)
        text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return LLMResult(
            content="\n".join(text_parts),
            model=selected_model,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )
