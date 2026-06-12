# PZ Deep Research

**English** | [简体中文](README.zh-CN.md)

A consumer-facing deep research web application. Its backend supports OpenAI, Claude, and Gemini while combining academic search, webpage retrieval, evidence extraction, source selection, and citation validation to produce structured reports with traceable sources.

The production interface exposes only the research question and Quick, Deep, or Expert mode. Backend routing currently fixes search planning and report writing to OpenAI `gpt-5.4-mini`, while evidence-card extraction uses `gpt-5-nano`. Provider/model selectors are hidden unless explicit internal manual mode is enabled.

> [!WARNING]
> This project is an experimental MVP. Model-generated content may contain omissions, errors, or inaccurate citations and should not be used directly for medical, legal, financial, or other high-stakes decisions.

## Key Features

- Supports OpenAI, Anthropic Claude, Google Gemini, and an offline mock provider on the backend.
- Searches academic sources through SerpAPI Google Scholar.
- Retrieves webpage content through Jina Reader and classifies evidence availability.
- Provides Quick, Deep, and Expert research modes.
- Streams model output, search activity, webpage visits, and evidence-processing progress.
- Uses compact evidence cards to control context size and reduce token growth in long-running tasks.
- Renders Markdown reports with Arabic-number inline citations, citation hover cards, and APA-style references.
- Exits through a bounded fallback path when sources or full-text evidence are insufficient, avoiding repeated visits and infinite loops.
- Persists research jobs, events, report drafts, and final reports in SQLite or PostgreSQL.
- Supports optional Clerk sign-in, automatic claiming of anonymous history, account-scoped history, and cross-device access while preserving guest mode.
- Exports the currently displayed report directly as a UTF-8 Markdown file.
- Generates paginated A4 PDF reports with task metadata and page numbers through backend Chromium.

## Research Pipeline

```text
User question
  -> Model generates English search queries
  -> SerpAPI Google Scholar search
  -> Runtime visits candidate sources concurrently
  -> Jina Reader returns webpage content
  -> Evidence cards are extracted and graded
  -> Final sources are selected by quality and relevance
  -> Model writes a report from the evidence cards
  -> Runtime validates length, citations, and References
  -> Results stream to the frontend over SSE
```

The Runtime controls webpage visits. The model only generates search queries and the final report; it does not autonomously loop over `visit` calls. This keeps tasks bounded, stabilizes citation numbering, and reduces duplicate retrieval.

The live production route is versioned as `openai-default-v1`. Client-supplied provider/model values are ignored in production mode; internal development can opt into manual routing with an environment variable.

## Research Modes

| Mode | Search strategy | Target final sources | Report body |
| --- | --- | ---: | ---: |
| Quick | 1 high-intent English query | 3 | 400-500 Chinese characters |
| Deep | 3 high-intent English queries | 10 | 1,300-1,500 Chinese characters |
| Expert | 2 search stages, 5 English queries per stage | 20 | 3,000-3,500 Chinese characters |

Actual source counts depend on search results and webpage accessibility. When the target cannot be reached, the system produces a degraded report from the available evidence and explicitly states the limitations.

## Tech Stack

- Frontend: Next.js 16, React 19, TypeScript
- Backend: FastAPI, Python
- Models: OpenAI API, Anthropic API, Google Gemini API
- Search: SerpAPI Google Scholar
- Web retrieval: Jina Reader
- Streaming: Server-Sent Events
- Database: SQLite (local default), PostgreSQL (production option), SQLAlchemy, Alembic
- Authentication: Clerk (optional, with local session JWT verification in FastAPI)
- Document export: Markdown Blob, Playwright Chromium PDF
- Verification: pytest, Playwright, ESLint, Next.js production build

## Repository Structure

```text
.
├── backend/              # FastAPI, Agent Runtime, providers, tools, and tests
├── frontend/             # Next.js research workspace
├── project-docs/         # Plans, product docs, architecture, tests, and changelog
├── .env.example          # Environment template without real credentials
├── .nvmrc                # Node.js version declaration
├── .python-version       # Python version declaration
├── LICENSE               # Apache License 2.0
├── NOTICE                # Attribution and upstream-reference notice
├── README.md             # English
└── README.zh-CN.md       # Simplified Chinese
```

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/PerryZzz-Pengyu/PZ_Deep_Research.git
cd PZ_Deep_Research
```

### 2. Prepare the runtime

Currently verified versions:

```text
Python 3.14.5
Node.js 24.16.0
npm 11.16.0
```

```bash
nvm use
python3 --version
node -v
npm -v
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

To run without real API credentials, keep:

```text
MODEL_ROUTING_MODE=manual
DEFAULT_PROVIDER=mock
SEARCH_PROVIDER=mock
```

A real research run requires:

- An API key for at least one of OpenAI, Anthropic, or Gemini.
- `SERPAPI_API_KEY`.
- `JINA_API_KEY` is recommended for more reliable webpage retrieval and higher service limits.

Never commit `.env`, `frontend/.env.local`, or real API credentials. See the [API key setup guide](project-docs/api-key-setup.md) for details.

Authentication is optional. To enable Clerk sign-in, configure:

```text
# frontend/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# .env
CLERK_JWT_KEY=
CLERK_AUTHORIZED_PARTIES=http://localhost:3000,http://127.0.0.1:3000
```

See the Chinese [authentication and history binding guide](project-docs/auth-setup.md). Without Clerk configuration, the application continues in browser-scoped guest mode.

The default production route is:

```text
MODEL_ROUTING_MODE=production
PRODUCTION_PROVIDER=openai
PRODUCTION_MODEL=gpt-5.4-mini
MODEL_ROUTING_VERSION=openai-default-v1
EVIDENCE_EXTRACTION_MODEL=gpt-5-nano
```

Local development stores data in `data/pz_deep_research.db` by default. For Neon PostgreSQL, use the pooled URL for application traffic and the direct URL for migrations and backups:

```text
DATABASE_URL=postgresql://user:password@pooled-host/database?sslmode=require
DATABASE_MIGRATION_URL=postgresql://user:password@direct-host/database?sslmode=require
```

Run `cd backend && PYTHONPATH=. .venv/bin/python scripts/check_database.py` to verify connectivity without printing credentials. Neon remains standard PostgreSQL, so the application can later move to another managed or self-hosted PostgreSQL service without rewriting the storage layer.

### 4. Start the backend

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
backend/.venv/bin/playwright install chromium
cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head && cd ..
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --reload-dir backend/app --port 8000
```

Linux production images can use `backend/.venv/bin/playwright install --with-deps chromium` to install Chromium and its system dependencies. The browser is stored in the Playwright user cache and is not committed to Git.

Health and readiness checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/readiness
```

### 5. Start the frontend

Open another terminal:

```bash
cd frontend
nvm use
npm ci
npm run dev
```

Open <http://localhost:3000>.

## Testing

Backend:

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
npm run test:e2e
```

See the [testing guide](project-docs/testing-guide.md) for the complete test strategy and manual acceptance flow. Project documentation is currently maintained in Chinese.

Latest local verification on June 11, 2026:

- 122 backend pytest cases passed.
- 7 Playwright Chromium end-to-end cases passed.
- The local `8000/3000` services and frontend smoke check passed without a Next.js error overlay or browser console errors.

## Privacy, Cost, and Security

- User questions are sent to the provider selected by the internal task configuration or model router. The current development UI allows manual selection; the production consumer UI is intended to hide it.
- Search queries are sent to SerpAPI; visited URLs and webpage content are processed through Jina Reader.
- API usage costs and third-party service quotas are the responsibility of the operator.
- Optional Clerk authentication is supported. FastAPI verifies Clerk session JWTs locally and uses the token `sub` as the trusted `user_id`.
- On first sign-in, jobs owned by the current browser visitor ID are claimed into the account and then become available across devices. Signing out does not return claimed jobs to guest history.
- Without Clerk configuration, history remains scoped to a browser-generated visitor ID. That identifier is not a security credential and should not be the only authorization boundary in a public deployment.
- Public deployments still require per-user quotas, rate limiting, abuse prevention, cost alerts, and correct production-domain values in `CLERK_AUTHORIZED_PARTIES`.
- SQLite is intended for local or single-instance use. Multi-instance production deployments should use PostgreSQL, backups, and a separate task worker.
- Never expose model, search, or webpage-retrieval API keys in client-side code.

## Upstream Reference and Independence

During its early design stage, PZ Deep Research referenced ideas from [Alibaba-NLP/DeepResearch](https://github.com/Alibaba-NLP/DeepResearch), including deep-research agent workflows, `search` / `visit` tool roles, and XML-style tool-call protocols.

This repository independently implements its Runtime, provider abstraction, evidence cards, source selection, citation validation, FastAPI service, and Next.js product interface. It does not depend on Qwen models or the `qwen-agent` package, and it does not distribute upstream model weights, datasets, or large assets.

PZ Deep Research is not an official product of, affiliated with, endorsed by, or sponsored by Alibaba-NLP, Qwen, OpenAI, Anthropic, Google, SerpAPI, or Jina AI. See [NOTICE](NOTICE) for details.

## Project Documentation

- [Project plan](project-docs/project-plan.md)
- [Product document](project-docs/product-doc.md)
- [Technical architecture](project-docs/technical-architecture.md)
- [Testing guide](project-docs/testing-guide.md)
- [Dependency management](project-docs/dependency-management.md)
- [API key setup](project-docs/api-key-setup.md)
- [Authentication and history binding](project-docs/auth-setup.md)
- [Changelog](project-docs/changelog.md)

## Contributing and Documentation

Run the backend tests, frontend lint, and production build before submitting changes. Any change to code, architecture, configuration, dependencies, interfaces, or product behavior must also be recorded in `project-docs/changelog.md`, with other project documents updated as needed.

## License

Licensed under the [Apache License 2.0](LICENSE).
