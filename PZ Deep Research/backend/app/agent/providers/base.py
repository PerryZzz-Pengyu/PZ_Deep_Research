from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.agent.schemas import LLMMessage, LLMResult


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
