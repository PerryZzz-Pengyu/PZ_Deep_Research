from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


ResearchMode = Literal["quick", "deep", "expert"]
ResearchStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ProviderName = Literal["mock", "openai", "anthropic", "gemini"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=8000)
    mode: ResearchMode = "deep"
    provider: Optional[ProviderName] = None
    model: Optional[str] = None
    # BYOK credentials (community edition). exclude=True keeps them out of
    # model_dump()/model_dump_json(), so they never reach persistence or SSE.
    api_key: Optional[str] = Field(default=None, exclude=True, repr=False)
    base_url: Optional[str] = Field(default=None, exclude=True, repr=False)


class ResearchEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    job_id: str
    type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ResearchJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    rerun_of_job_id: Optional[str] = None
    routing_version: Optional[str] = None
    query: str
    mode: ResearchMode
    provider: str
    model: Optional[str] = None
    status: ResearchStatus = "queued"
    draft_report: str = ""
    final_report: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_retryable: bool = False
    error_stage: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResult(BaseModel):
    content: str
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMStreamEvent(BaseModel):
    type: Literal["delta", "done"]
    delta: str = ""
    result: Optional[LLMResult] = None


class ToolResult(BaseModel):
    name: str
    content: str
    sources: list[dict[str, str]] = Field(default_factory=list)
    # url -> 该来源的完整正文（仅供 Runtime 做证据卡片抽取，不会写入事件或前端快照）。
    source_texts: dict[str, str] = Field(default_factory=dict)
