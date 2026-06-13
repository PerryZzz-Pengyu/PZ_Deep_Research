# Contributing to PZ Deep Research

Thanks for your interest in contributing! This repository is the **Community Edition** of PZ Deep Research — a complete, self-hostable single-user research tool. Cloud/commercial code is not part of this repo.

## Ground rules

- Be respectful and constructive.
- Keep changes focused; one logical change per pull request.
- Match the style and conventions of the surrounding code.

## Development workflow

This project follows a **test-first** rhythm: define how a change is verified before implementing it.

1. Describe the behavior you are adding or fixing.
2. Add or update tests (backend `pytest`, frontend Playwright) first.
3. Run the tests and confirm the new ones fail before implementation.
4. Implement the change.
5. Re-run until green.
6. Record the change in `project-docs/changelog.md` and update related docs.

### Before submitting

Run all of the following and make sure they pass:

```bash
# Backend
cd backend && .venv/bin/python -m pytest

# Secret guard (must stay clean)
backend/.venv/bin/python backend/scripts/check_no_secrets_tracked.py

# Frontend
cd frontend && npm run lint && npm run build && npm run test:e2e
```

Any change to code, architecture, configuration, dependencies, interfaces, or product behavior **must** be recorded in [`project-docs/changelog.md`](project-docs/changelog.md), using a `YYYY-MM-DD HH:mm 时区` heading. Update [`project-docs/testing-guide.md`](project-docs/testing-guide.md) when you add or change tests.

### Optional: secret guard as a pre-commit hook

To catch accidental commits of private business material locally:

```bash
ln -s ../../backend/scripts/check_no_secrets_tracked.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Security and secrets

- Never commit API keys, `.env` files, or private business material.
- Commercially sensitive docs (`project-docs/business-model.md`, `project-docs/private/`) are gitignored and enforced by `backend/scripts/check_no_secrets_tracked.py`.
- BYOK credentials must never be persisted, logged, or sent over SSE.

## Contributor License Agreement (CLA)

By submitting a contribution, you agree to the terms in [CLA.md](CLA.md). This keeps the project's licensing options open (the Community Edition is Apache 2.0 today).

## License

Contributions to this repository are licensed under the [Apache License 2.0](LICENSE).
