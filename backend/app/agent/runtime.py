"""Compatibility exports for the academic research runtime."""

from app.research.domains.academic.runtime import (
    AcademicRuntime,
    MODE_POLICIES,
    TagContentStream,
)

AgentRuntime = AcademicRuntime

__all__ = ["AcademicRuntime", "AgentRuntime", "MODE_POLICIES", "TagContentStream"]
