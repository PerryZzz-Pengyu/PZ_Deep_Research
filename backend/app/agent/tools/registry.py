from __future__ import annotations

from typing import Any

from app.agent.schemas import ToolResult
from app.agent.tools.base import AgentTool


class ToolRegistry:
    def __init__(self, tools: list[AgentTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(name=name, content=f"[tool] 未知工具：{name}")
        return await tool.call(arguments)

    def names(self) -> list[str]:
        return sorted(self._tools)
