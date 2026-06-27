from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.agent.schemas import ResearchRequest
from app.research.registry import DomainRegistry, UnsupportedResearchDomainError
from app.storage import InMemoryJobStore


class StubRuntime:
    async def run(self, job_id: str, request: ResearchRequest):
        if False:
            yield None

    async def resume_report(
        self,
        job_id: str,
        request: ResearchRequest,
        retry_context: dict[str, object],
    ):
        if False:
            yield None


def test_research_request_defaults_to_academic_domain() -> None:
    request = ResearchRequest(query="default domain", mode="quick", provider="mock")

    assert request.domain == "academic"


def test_research_request_accepts_explicit_academic_domain() -> None:
    request = ResearchRequest(
        domain="academic",
        query="explicit domain",
        mode="quick",
        provider="mock",
    )

    assert request.domain == "academic"


def test_research_request_rejects_unimplemented_domain() -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(
            domain="finance",
            query="finance is not implemented yet",
            mode="quick",
            provider="mock",
        )


def test_in_memory_store_preserves_request_domain() -> None:
    async def run_scenario():
        store = InMemoryJobStore()
        request = ResearchRequest(
            domain="academic",
            query="persist domain",
            mode="quick",
            provider="mock",
        )
        created = await store.create_job(request, provider="mock")
        restored = await store.get_job(created.id)
        return created, restored

    created, restored = asyncio.run(run_scenario())

    assert created.domain == "academic"
    assert restored is not None
    assert restored.domain == "academic"


def test_domain_registry_resolves_registered_runtime_lazily() -> None:
    runtime = StubRuntime()
    resolutions = 0

    def resolve_runtime() -> StubRuntime:
        nonlocal resolutions
        resolutions += 1
        return runtime

    registry = DomainRegistry({"academic": resolve_runtime})

    assert resolutions == 0
    assert registry.resolve("academic") is runtime
    assert resolutions == 1


def test_domain_registry_rejects_unregistered_domain() -> None:
    registry = DomainRegistry({"academic": StubRuntime})

    with pytest.raises(UnsupportedResearchDomainError, match="finance"):
        registry.resolve("finance")
