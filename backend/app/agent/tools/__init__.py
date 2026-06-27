from app.agent.tools.registry import ToolRegistry

__all__ = ["ToolRegistry", "build_default_tool_registry"]


def __getattr__(name: str):
    if name == "build_default_tool_registry":
        from app.research.domains.academic.tools import build_academic_tool_registry

        return build_academic_tool_registry
    raise AttributeError(name)
