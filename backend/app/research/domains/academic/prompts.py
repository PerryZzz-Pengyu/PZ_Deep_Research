from __future__ import annotations

"""Academic research prompt loading and mode guidance."""

from pathlib import Path


PROMPT_TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")


def _load_prompt(filename: str) -> str:
    return (PROMPT_TEMPLATE_DIR / filename).read_text(encoding="utf-8").strip()


SYSTEM_PROMPT = _load_prompt("system_prompt.en.md")
SYSTEM_PROMPT_ZH_FOR_REVIEW = _load_prompt("system_prompt.zh-CN.md")


MODE_GUIDANCE = {
    "quick": (
        "Quick mode: use exactly 1 high-intent English search query, visit 3 key sources, "
        "then write a concise essay-style report with 350-900 Chinese body characters, excluding references."
    ),
    "deep": (
        "Deep mode: use exactly 3 high-intent English search queries, visit 10 key sources, "
        "then write a literature-review-style report with 1100-2600 Chinese body characters, excluding references."
    ),
    "expert": (
        "Expert mode: run search and visit, synthesize preliminary findings, review evidence gaps, "
        "run a second search with exactly 5 high-intent English search queries, visit 20 key sources in total, "
        "then write a paper-style final report with 2700-5200 Chinese body characters, excluding references."
    ),
}


def build_user_prompt(query: str, mode: str) -> str:
    mode_guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE["deep"])
    return f"""Selected research mode: {mode}

Mode execution policy:
{mode_guidance}

Pipeline reminder: search -> visit -> answer. You only emit the search query now; the system visits the most relevant sources for you and returns evidence cards, then asks you to write the report. Do not emit visit calls and do not answer before the system requests the report.

User question:
{query}
"""
