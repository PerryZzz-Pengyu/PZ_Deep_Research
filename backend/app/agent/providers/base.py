from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Optional

from app.agent.schemas import LLMMessage, LLMResult, LLMStreamEvent


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult:
        """Generate one assistant response from chat messages."""

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMStreamEvent]:
        result = await self.generate(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield LLMStreamEvent(type="done", result=result)
