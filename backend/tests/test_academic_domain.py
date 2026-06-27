from __future__ import annotations

from app.agent.evidence import EvidenceCard as LegacyEvidenceCard
from app.agent.prompts import SYSTEM_PROMPT as LEGACY_SYSTEM_PROMPT
from app.agent.runtime import AgentRuntime, MODE_POLICIES as LEGACY_MODE_POLICIES
from app.agent.selection import select_sources as legacy_select_sources
from app.agent.tools import build_default_tool_registry
from app.agent.tools.search import SearchTool as LegacySearchTool
from app.api import routes
from app.research.domains.academic import AcademicRuntime, build_academic_tool_registry
from app.research.domains.academic.evidence import EvidenceCard
from app.research.domains.academic.prompts import PROMPT_TEMPLATE_DIR, SYSTEM_PROMPT
from app.research.domains.academic.runtime import MODE_POLICIES
from app.research.domains.academic.search import SearchTool
from app.research.domains.academic.selection import select_sources


def test_academic_domain_owns_runtime_while_legacy_import_remains_compatible() -> None:
    assert AgentRuntime is AcademicRuntime
    assert AcademicRuntime.__module__ == "app.research.domains.academic.runtime"
    assert LEGACY_MODE_POLICIES is MODE_POLICIES


def test_academic_domain_owns_prompts_evidence_selection_and_search() -> None:
    assert LEGACY_SYSTEM_PROMPT is SYSTEM_PROMPT
    assert LegacyEvidenceCard is EvidenceCard
    assert legacy_select_sources is select_sources
    assert LegacySearchTool is SearchTool
    assert PROMPT_TEMPLATE_DIR.parent.name == "academic"
    assert SearchTool.__module__ == "app.research.domains.academic.search"


def test_legacy_tool_builder_is_academic_builder_alias() -> None:
    assert build_default_tool_registry is build_academic_tool_registry


def test_routes_register_the_academic_runtime_from_the_domain_package() -> None:
    assert isinstance(routes.runtime, AcademicRuntime)
    assert routes.domain_registry.resolve("academic") is routes.runtime
