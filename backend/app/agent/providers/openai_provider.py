from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.schemas import LLMMessage, LLMResult, LLMStreamEvent


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "",
    ) -> None:
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

        client_kwargs = {"api_key": self.api_key, "base_url": self.base_url or "https://api.openai.com/v1"}
        client = AsyncOpenAI(**client_kwargs)
        selected_model = model or self.default_model
        if not selected_model:
            raise RuntimeError("OPENAI_MODEL 未配置")

        system_parts, input_messages = self._build_response_input(messages)

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
    def _build_response_input(messages: list[LLMMessage]) -> tuple[list[str], list[dict[str, str]]]:
        system_parts = [message.content for message in messages if message.role == "system"]
        input_messages: list[dict[str, str]] = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        ]
        return system_parts, input_messages

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMStreamEvent]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置")

        from openai import AsyncOpenAI

        client_kwargs = {"api_key": self.api_key, "base_url": self.base_url or "https://api.openai.com/v1"}
        client = AsyncOpenAI(**client_kwargs)
        selected_model = model or self.default_model
        if not selected_model:
            raise RuntimeError("OPENAI_MODEL 未配置")

        system_parts, input_messages = self._build_response_input(messages)
        stream = await client.responses.create(
            model=selected_model,
            instructions="\n\n".join(system_parts) or None,
            input=input_messages,
            temperature=temperature,
            max_output_tokens=max_tokens,
            stream=True,
        )

        text_parts: list[str] = []
        final_result: LLMResult | None = None
        async for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    text_parts.append(delta)
                    yield LLMStreamEvent(type="delta", delta=delta)
            elif event_type == "response.completed":
                response = getattr(event, "response", None)
                content = getattr(response, "output_text", "") or "".join(text_parts)
                usage = getattr(response, "usage", None)
                final_result = LLMResult(
                    content=content,
                    model=selected_model,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                )
            elif event_type == "error":
                error = getattr(event, "error", None)
                message = getattr(error, "message", "OpenAI streaming error")
                raise RuntimeError(message)
            elif event_type == "response.failed":
                response = getattr(event, "response", None)
                error = getattr(response, "error", None)
                message = getattr(error, "message", "OpenAI streaming failed")
                raise RuntimeError(message)
            elif event_type == "response.incomplete":
                response = getattr(event, "response", None)
                details = getattr(response, "incomplete_details", None)
                reason = getattr(details, "reason", "unknown")
                raise RuntimeError(f"OpenAI streaming incomplete: {reason}")

        yield LLMStreamEvent(
            type="done",
            result=final_result or LLMResult(content="".join(text_parts), model=selected_model),
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
