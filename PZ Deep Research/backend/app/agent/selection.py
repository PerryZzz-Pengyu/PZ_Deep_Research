from __future__ import annotations

from dataclasses import dataclass


# 证据强度分层：数字越小越优先。用于「full_text 优先 > 相关性」的选源排序。
_EVIDENCE_TIER = {
    "full_text": 0,
    "partial_text": 1,
    "metadata": 2,
    "metadata_only": 2,
}
_FALLBACK_TIER = 3  # failed / unavailable / mock 等无证据来源排最后


def _evidence_value(source: dict[str, str]) -> str:
    return source.get("evidence_level") or source.get("read_status") or ""


def is_full_text(source: dict[str, str]) -> bool:
    return source.get("evidence_level") == "full_text" or source.get("read_status") == "full_text"


def count_full_text(sources: list[dict[str, str]]) -> int:
    return sum(1 for source in sources if is_full_text(source))


def should_stop_visiting(full_text_count: int, target: int) -> bool:
    """访问队列早停判据：已拿到的全文证据数达到本模式目标即可短路。"""
    return full_text_count >= target


@dataclass(frozen=True)
class SelectionResult:
    selected: list[dict[str, str]]
    target: int
    total_available: int
    full_text_count: int
    degraded: bool  # 总来源数不足目标 → 逃生降级，有多少用多少
    full_text_shortfall: bool  # 全文证据数不足目标 → 报告需说明部分结论基于摘要/受限证据


def select_sources(sources: list[dict[str, str]], target: int) -> SelectionResult:
    """从已访问来源里按「全文证据优先 > 相关性（输入即搜索原生序）」选出本模式所需数量。

    - 总数 >= 目标：取排序后的前 target 个；
    - 总数 < 目标：逃生降级，全部返回（仍按质量排序），degraded=True。
    """
    # 稳定排序：先按证据分层，再按原始相关性顺序（输入下标）。
    ordered = [
        source
        for _, source in sorted(
            enumerate(sources),
            key=lambda pair: (_EVIDENCE_TIER.get(_evidence_value(pair[1]), _FALLBACK_TIER), pair[0]),
        )
    ]

    total_available = len(sources)
    full_text_count = count_full_text(sources)

    if total_available <= target:
        selected = ordered
        degraded = total_available < target
    else:
        selected = ordered[:target]
        degraded = False

    return SelectionResult(
        selected=selected,
        target=target,
        total_available=total_available,
        full_text_count=full_text_count,
        degraded=degraded,
        full_text_shortfall=full_text_count < target,
    )
