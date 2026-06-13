from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_no_secrets_tracked.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    (repo / ".gitignore").write_text(
        "# Private business planning.\n"
        "project-docs/business-model.md\n"
        "project-docs/private/\n",
        encoding="utf-8",
    )
    docs = repo / "project-docs"
    docs.mkdir()
    (docs / "product-doc.md").write_text("public doc\n", encoding="utf-8")
    (docs / "business-model.md").write_text("SECRET pricing\n", encoding="utf-8")
    (docs / "private").mkdir()
    (docs / "private" / "notes.md").write_text("SECRET notes\n", encoding="utf-8")


def _run_guard(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_guard_passes_when_secret_docs_not_tracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _git(tmp_path, "add", "project-docs/product-doc.md", ".gitignore")

    result = _run_guard(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_guard_fails_when_secret_file_staged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # Force-add the gitignored business doc to simulate an accidental commit.
    _git(tmp_path, "add", "-f", "project-docs/business-model.md")

    result = _run_guard(tmp_path)

    assert result.returncode != 0
    assert "business-model.md" in (result.stdout + result.stderr)


def test_guard_fails_when_private_dir_tracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _git(tmp_path, "add", "-f", "project-docs/private/notes.md")
    _git(tmp_path, "commit", "-m", "oops")

    result = _run_guard(tmp_path)

    assert result.returncode != 0
    assert "private" in (result.stdout + result.stderr)


def test_guard_fails_when_sensitive_doc_is_renamed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    pricing = tmp_path / "project-docs" / "pricing.md"
    pricing.write_text("commercial pricing details\n", encoding="utf-8")
    _git(tmp_path, "add", "-f", "project-docs/pricing.md")

    result = _run_guard(tmp_path)

    assert result.returncode != 0
    assert "pricing.md" in (result.stdout + result.stderr)


def test_guard_fails_when_private_marker_moves_to_another_name(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    notes = tmp_path / "project-docs" / "notes.md"
    notes.write_text(
        "> 私有商业资料：本文件不得加入 Git、不得推送到公开仓库。\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "project-docs/notes.md")

    result = _run_guard(tmp_path)

    assert result.returncode != 0
    assert "notes.md" in (result.stdout + result.stderr)


def test_guard_allows_public_code_file_with_sensitive_word(tmp_path: Path) -> None:
    # The sensitive-name heuristic targets business docs under project-docs/.
    # A public UI/code file such as a pricing page must not be flagged.
    _init_repo(tmp_path)
    page = tmp_path / "frontend" / "src" / "components" / "pricing.tsx"
    page.parent.mkdir(parents=True)
    page.write_text("export function Pricing() { return null; }\n", encoding="utf-8")
    _git(tmp_path, "add", "frontend/src/components/pricing.tsx")

    result = _run_guard(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
