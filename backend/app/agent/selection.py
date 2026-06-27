"""Compatibility exports for academic source selection."""

from app.research.domains.academic.selection import (
    SelectionResult,
    count_full_text,
    is_full_text,
    select_sources,
    should_stop_visiting,
)

__all__ = [
    "SelectionResult",
    "count_full_text",
    "is_full_text",
    "select_sources",
    "should_stop_visiting",
]
