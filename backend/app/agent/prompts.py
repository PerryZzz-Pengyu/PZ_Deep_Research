"""Compatibility exports for the academic prompt implementation."""

from app.research.domains.academic.prompts import (
    MODE_GUIDANCE,
    PROMPT_TEMPLATE_DIR,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_ZH_FOR_REVIEW,
    build_user_prompt,
)

__all__ = [
    "MODE_GUIDANCE",
    "PROMPT_TEMPLATE_DIR",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_ZH_FOR_REVIEW",
    "build_user_prompt",
]
