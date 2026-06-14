from __future__ import annotations

from typing import Optional

from app.agent.providers.base import LLMProvider
from app.agent.schemas import LLMMessage, LLMResult


class GeminiProvider(LLMProvider):
    name = "gemini"

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
            raise RuntimeError("GEMINI_API_KEY 未配置")

        from google import genai
        from google.genai import types

        selected_model = model or self.default_model
        if not selected_model:
            raise RuntimeError("GEMINI_MODEL 未配置")

        prompt = "\n\n".join(f"{message.role}: {message.content}" for message in messages)
        client = genai.Client(api_key=self.api_key)
        try:
            response = await client.aio.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
        finally:
            await client.aio.aclose()
        usage = getattr(response, "usage_metadata", None)
        return LLMResult(
            content=response.text or "",
            model=selected_model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
        )
