from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agent.schemas import ToolResult


class AgentTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool and return text plus optional sources."""
