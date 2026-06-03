from __future__ import annotations

from typing import Any
from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.schemas import LLMMessage, LLMResult


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str = "", default_model: str = "") -> None:
        self.api_key = api_key
        self.base_url = base_url
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
            raise RuntimeError("OPENAI_API_KEY 未配置")

        from openai import AsyncOpenAI

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = AsyncOpenAI(**client_kwargs)
        selected_model = model or self.default_model
        if not selected_model:
            raise RuntimeError("OPENAI_MODEL 未配置")

        system_parts = [message.content for message in messages if message.role == "system"]
        input_messages: list[dict[str, str]] = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        ]

        response = await client.responses.create(
            model=selected_model,
            instructions="\n\n".join(system_parts) or None,
            input=input_messages,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        content = getattr(response, "output_text", "") or self._extract_response_text(response)
        usage = getattr(response, "usage", None)
        return LLMResult(
            content=content,
            model=selected_model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        text_parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
