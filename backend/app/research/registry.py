from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from typing import Protocol

from app.agent.schemas import ResearchEvent, ResearchRequest


class ResearchDomainRuntime(Protocol):
    def run(
        self,
        job_id: str,
        request: ResearchRequest,
    ) -> AsyncIterator[ResearchEvent]: ...

    def resume_report(
        self,
        job_id: str,
        request: ResearchRequest,
        retry_context: dict[str, object],
    ) -> AsyncIterator[ResearchEvent]: ...


RuntimeResolver = Callable[[], ResearchDomainRuntime]


class UnsupportedResearchDomainError(LookupError):
    pass


class DomainRegistry:
    """Resolve a bounded domain runtime without coupling the job core to domain logic."""

    def __init__(
        self,
        runtimes: Mapping[str, RuntimeResolver] | None = None,
    ) -> None:
        self._runtimes = dict(runtimes or {})

    def register(self, domain: str, resolver: RuntimeResolver) -> None:
        normalized = domain.strip().lower()
        if not normalized:
            raise ValueError("Research domain cannot be empty")
        self._runtimes[normalized] = resolver

    def resolve(self, domain: str) -> ResearchDomainRuntime:
        normalized = domain.strip().lower()
        resolver = self._runtimes.get(normalized)
        if resolver is None:
            raise UnsupportedResearchDomainError(
                f"Unsupported research domain: {domain}"
            )
        return resolver()
