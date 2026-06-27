"""Compatibility exports for academic evidence extraction."""

from app.research.domains.academic.evidence import (
    EvidenceCard,
    EvidenceExtractor,
    build_extraction_prompt,
    render_card,
)

__all__ = [
    "EvidenceCard",
    "EvidenceExtractor",
    "build_extraction_prompt",
    "render_card",
]
