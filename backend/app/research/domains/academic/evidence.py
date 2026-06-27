from __future__ import annotations

"""Academic webpage evidence-card extraction."""

import asyncio
from dataclasses import dataclass
from typing import Optional, Protocol

from app.agent.schemas import LLMMessage, LLMResult


class _Provider(Protocol):
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResult: ...


@dataclass(frozen=True)
class EvidenceCard:
    citation_id: str
    title: str
    url: str
    evidence_level: str
    content: str
    extraction_status: str = "extracted"


def build_extraction_prompt(
    *,
    goal: str,
    citation_id: str,
    title: str,
    url: str,
    raw_text: str,
) -> list[LLMMessage]:
    """构造证据卡片抽取提示词。硬约束逐字摘录、禁止编造，保住学术引用准确性。"""
    system = (
        "你是 PZ Deep Research 的证据抽取助手。你的唯一任务是从给定的单篇网页正文中，"
        "围绕研究目标抽取可用于撰写报告的关键证据，整理成一张紧凑的证据卡片。\n"
        "硬性约束：\n"
        "1. 只能依据给定正文，禁止编造正文之外的任何信息、数字、作者或结论。\n"
        "2. 关键数字、疗效、安全性、样本量、人群和结论必须逐字摘录原文，禁止改写或四舍五入数字。\n"
        "3. 卡片里引用该来源时统一使用其来源编号角标。\n"
        "4. 输出尽量精简（控制在要点列表内），只保留与研究目标相关的证据。"
    )
    user = (
        f"研究目标：{goal or '未指定'}\n"
        f"来源编号：[{citation_id}]\n"
        f"标题：{title}\n"
        f"URL：{url}\n"
        "网页正文如下（只能依据它抽取，引用时用 "
        f"[{citation_id}]）：\n"
        "<page>\n"
        f"{raw_text}\n"
        "</page>\n"
        "请输出该来源的证据卡片（要点列表，含逐字关键数字/结论）。"
    )
    return [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]


def render_card(card: EvidenceCard) -> str:
    """把证据卡片渲染成注入模型上下文的紧凑文本。"""
    return (
        f"[{card.citation_id}] {card.title}（证据强度：{card.evidence_level}）\n"
        f"{card.url}\n"
        f"{card.content}"
    )


class EvidenceExtractor:
    """把每条已访问来源的正文抽成紧凑证据卡片：长正文走便宜模型抽取，短摘要直接透传。"""

    def __init__(
        self,
        provider: _Provider,
        *,
        model: Optional[str] = None,
        min_extract_chars: int = 800,
        max_output_chars: int = 1200,
        max_concurrency: int = 5,
        max_retries: int = 1,
        timeout_seconds: float = 45.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.min_extract_chars = max(1, min_extract_chars)
        self.max_output_chars = max(1, max_output_chars)
        self.max_concurrency = max(1, max_concurrency)
        self.max_retries = max(0, max_retries)
        self.timeout_seconds = max(0.1, timeout_seconds)

    async def extract(
        self,
        source: dict[str, str],
        raw_text: str,
        *,
        goal: str,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> EvidenceCard:
        citation_id = source.get("citation_id", "")
        title = source.get("title", source.get("url", ""))
        url = source.get("url", "")
        evidence_level = source.get("evidence_level") or source.get("read_status") or ""
        text = (raw_text or "").strip()

        # 短文本（摘要/题录/受限/失败）不值得调用模型，直接透传，省成本。
        if len(text) < self.min_extract_chars:
            fallback = text or source.get("content_preview", "") or source.get("snippet", "")
            return EvidenceCard(
                citation_id=citation_id,
                title=title,
                url=url,
                evidence_level=evidence_level,
                content=fallback.strip()[: self.max_output_chars],
                extraction_status="passthrough",
            )

        messages = build_extraction_prompt(
            goal=goal,
            citation_id=citation_id,
            title=title,
            url=url,
            raw_text=text,
        )

        async def _run_with_retries() -> Optional[LLMResult]:
            for _ in range(self.max_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        self.provider.generate(messages, model=self.model, temperature=0.0),
                        timeout=self.timeout_seconds,
                    )
                    if result.content.strip():
                        return result
                except Exception:
                    continue
            return None

        if semaphore is not None:
            async with semaphore:
                result = await _run_with_retries()
        else:
            result = await _run_with_retries()

        if result is None:
            fallback = text or source.get("content_preview", "") or source.get("snippet", "")
            return EvidenceCard(
                citation_id=citation_id,
                title=title,
                url=url,
                evidence_level=evidence_level,
                content=fallback.strip()[: self.max_output_chars],
                extraction_status="fallback",
            )

        return EvidenceCard(
            citation_id=citation_id,
            title=title,
            url=url,
            evidence_level=evidence_level,
            content=result.content.strip()[: self.max_output_chars],
            extraction_status="extracted",
        )

    async def extract_many(
        self,
        sources: list[dict[str, str]],
        raw_by_url: dict[str, str],
        *,
        goal: str,
    ) -> list[EvidenceCard]:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        cards = await asyncio.gather(
            *(
                self.extract(source, raw_by_url.get(source.get("url", ""), ""), goal=goal, semaphore=semaphore)
                for source in sources
            )
        )
        return list(cards)
