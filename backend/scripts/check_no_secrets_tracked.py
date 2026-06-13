"""Guard against committing private business material to the public repo.

The community repo keeps commercially sensitive docs out of version control via
``.gitignore``. ``.gitignore`` alone is fragile: a force-add or a renamed path
can slip secrets into history. This guard fails when any secret path is tracked
or staged, so it can run in CI or as an optional pre-commit hook.

Usage::

    python backend/scripts/check_no_secrets_tracked.py [--repo-root PATH]

Exit code 0 when clean, 1 when a secret path is tracked or staged.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Paths (relative to the repo root) that must never enter the public repo.
# Keep this list in sync with the "Private business planning" block in .gitignore.
SECRET_FILES: tuple[str, ...] = ("project-docs/business-model.md",)
SECRET_DIRS: tuple[str, ...] = ("project-docs/private/",)


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def repo_root(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def _is_secret(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in SECRET_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in SECRET_DIRS)


def find_violations(root: Path) -> list[str]:
    """Return secret paths that are tracked or staged in the repo at ``root``."""
    candidates: set[str] = set()
    candidates.update(_git_lines(root, "ls-files"))
    candidates.update(_git_lines(root, "diff", "--cached", "--name-only"))
    return sorted(path for path in candidates if _is_secret(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to check (defaults to the git toplevel of the cwd).",
    )
    args = parser.parse_args(argv)

    root = args.repo_root or repo_root()
    violations = find_violations(root)
    if violations:
        print("ERROR: private business material is tracked or staged:")
        for path in violations:
            print(f"  - {path}")
        print(
            "These paths are commercially sensitive and must stay out of the "
            "public repo. Run `git rm --cached <path>` and keep them ignored."
        )
        return 1
    print("OK: no private business material is tracked or staged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
