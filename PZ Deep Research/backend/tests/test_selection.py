from __future__ import annotations

from app.agent.selection import (
    count_full_text,
    select_sources,
    should_stop_visiting,
)


def make_source(url: str, evidence_level: str, *, read_status: str | None = None) -> dict[str, str]:
    source = {"url": url, "title": url, "evidence_level": evidence_level}
    if read_status is not None:
        source["read_status"] = read_status
    return source


def test_count_full_text_counts_evidence_level_and_read_status() -> None:
    sources = [
        make_source("https://a", "full_text"),
        make_source("https://b", "metadata_only"),
        make_source("https://c", "x", read_status="full_text"),
        make_source("https://d", "partial_text"),
    ]
    assert count_full_text(sources) == 2


def test_should_stop_visiting_when_full_text_reaches_target() -> None:
    assert should_stop_visiting(3, 3) is True
    assert should_stop_visiting(4, 3) is True
    assert should_stop_visiting(2, 3) is False


def test_select_sources_orders_full_text_first_preserving_relevance() -> None:
    # 输入按相关性顺序（搜索原生序）：第 0、2 是全文，第 1、3 是受限
    sources = [
        make_source("https://r0", "metadata_only"),
        make_source("https://r1", "full_text"),
        make_source("https://r2", "metadata_only"),
        make_source("https://r3", "full_text"),
        make_source("https://r4", "metadata_only"),
    ]
    result = select_sources(sources, target=3)

    # 取前 3：full_text 优先（保各自相关性序），再补相关性最高的受限来源
    assert [s["url"] for s in result.selected] == ["https://r1", "https://r3", "https://r0"]
    assert result.target == 3
    assert result.total_available == 5
    assert result.full_text_count == 2
    assert result.degraded is False
    # full_text(2) < target(3)，应标记全文证据不足
    assert result.full_text_shortfall is True


def test_select_sources_not_full_text_shortfall_when_enough_full_text() -> None:
    sources = [
        make_source("https://a", "full_text"),
        make_source("https://b", "full_text"),
        make_source("https://c", "full_text"),
        make_source("https://d", "metadata_only"),
    ]
    result = select_sources(sources, target=3)
    assert [s["url"] for s in result.selected] == ["https://a", "https://b", "https://c"]
    assert result.full_text_count == 3
    assert result.full_text_shortfall is False
    assert result.degraded is False


def test_select_sources_escape_hatch_when_fewer_than_target() -> None:
    # 总来源数不够目标 → 逃生降级：有多少用多少，degraded=True
    sources = [
        make_source("https://a", "metadata_only"),
        make_source("https://b", "full_text"),
    ]
    result = select_sources(sources, target=10)
    assert {s["url"] for s in result.selected} == {"https://a", "https://b"}
    # 仍按 full_text 优先排序
    assert [s["url"] for s in result.selected] == ["https://b", "https://a"]
    assert result.total_available == 2
    assert result.degraded is True
    assert result.full_text_shortfall is True


def test_select_sources_ranks_usable_above_failed() -> None:
    # 受限/部分正文应排在失败/不可用之前
    sources = [
        make_source("https://failed", "unavailable", read_status="failed"),
        make_source("https://meta", "metadata_only"),
        make_source("https://partial", "partial_text"),
    ]
    result = select_sources(sources, target=2)
    # 取前 2：partial_text 与 metadata_only 优先于 failed
    assert [s["url"] for s in result.selected] == ["https://partial", "https://meta"]
    assert result.degraded is False
