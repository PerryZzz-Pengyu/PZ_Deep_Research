from __future__ import annotations

import asyncio

from app.agent.evidence import (
    EvidenceCard,
    EvidenceExtractor,
    build_extraction_prompt,
    render_card,
)
from app.agent.schemas import LLMResult


class FakeProvider:
    name = "fake"

    def __init__(self, output: str = "关键数据：体重下降 12.4%（原文数据）[1]") -> None:
        self.output = output
        self.calls: list[dict] = []

    async def generate(self, messages, *, model=None, temperature=0.3, max_tokens=4096):
        self.calls.append({"messages": messages, "model": model})
        return LLMResult(content=self.output, model=model)


def make_source(url, citation_id, evidence_level, *, title="标题", read_status=None, snippet="", content_preview=""):
    source = {
        "url": url,
        "citation_id": citation_id,
        "title": title,
        "evidence_level": evidence_level,
        "snippet": snippet,
        "content_preview": content_preview,
    }
    if read_status is not None:
        source["read_status"] = read_status
    return source


def test_build_extraction_prompt_includes_goal_id_text_and_constraints() -> None:
    messages = build_extraction_prompt(
        goal="对比 GLP-1 减重疗效",
        citation_id="3",
        title="Semaglutide RCT",
        url="https://example.org/paper",
        raw_text="患者在 68 周后平均减重 14.9%（p<0.001）。",
    )
    blob = "\n".join(m.content for m in messages)
    assert "对比 GLP-1 减重疗效" in blob
    assert "14.9%" in blob  # 原文必须进入提示词
    assert "[3]" in blob  # 必须告知来源编号
    # 关键约束：逐字摘录、禁止编造
    assert "逐字" in blob
    assert "编造" in blob


def test_extract_uses_llm_for_long_full_text_source() -> None:
    provider = FakeProvider()
    extractor = EvidenceExtractor(provider, model="gpt-5-nano", min_extract_chars=800)
    source = make_source("https://example.org/a", "1", "full_text")
    raw = "正文。" * 600  # 远超阈值

    card = asyncio.run(extractor.extract(source, raw, goal="目标"))

    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == "gpt-5-nano"
    assert isinstance(card, EvidenceCard)
    assert card.citation_id == "1"
    assert card.url == "https://example.org/a"
    assert card.evidence_level == "full_text"
    assert card.content == provider.output


def test_extract_passthrough_for_short_metadata_source_without_llm() -> None:
    provider = FakeProvider()
    extractor = EvidenceExtractor(provider, model="gpt-5-nano", min_extract_chars=800)
    source = make_source(
        "https://example.org/b",
        "2",
        "metadata_only",
        snippet="这是一段简短摘要。",
        content_preview="这是一段简短摘要。",
    )

    card = asyncio.run(extractor.extract(source, "这是一段简短摘要。", goal="目标"))

    assert len(provider.calls) == 0  # 短摘要不调用模型，省成本
    assert card.citation_id == "2"
    assert card.evidence_level == "metadata_only"
    assert "简短摘要" in card.content


def test_extract_many_preserves_order_and_only_extracts_long_sources() -> None:
    provider = FakeProvider()
    extractor = EvidenceExtractor(provider, model="gpt-5-nano", min_extract_chars=800)
    sources = [
        make_source("https://example.org/1", "1", "full_text"),
        make_source("https://example.org/2", "2", "metadata_only", snippet="短摘要"),
        make_source("https://example.org/3", "3", "full_text"),
    ]
    raw_by_url = {
        "https://example.org/1": "正文。" * 600,
        "https://example.org/2": "短摘要",
        "https://example.org/3": "正文。" * 600,
    }

    cards = asyncio.run(extractor.extract_many(sources, raw_by_url, goal="目标"))

    assert [c.citation_id for c in cards] == ["1", "2", "3"]  # 保序
    assert len(provider.calls) == 2  # 只有两条长全文走了模型


def test_render_card_is_compact_and_cites_id() -> None:
    card = EvidenceCard(
        citation_id="2",
        title="Liraglutide 综述",
        url="https://example.org/x",
        evidence_level="full_text",
        content="样本 3731 人，平均减重 8.0kg。",
    )
    rendered = render_card(card)
    assert "[2]" in rendered
    assert "Liraglutide 综述" in rendered
    assert "https://example.org/x" in rendered
    assert "8.0kg" in rendered
    assert "full_text" in rendered
