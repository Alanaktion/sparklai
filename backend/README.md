# SparklAI backend (FastAPI)

See [`../BACKEND_MIGRATION.md`](../BACKEND_MIGRATION.md) for what's ported here vs. still on the
SvelteKit side, and why.

## Setup

```bash
cd backend
uv sync --extra dev
cp .env.example .env   # edit SESSION_SECRET at minimum; DATABASE_URL defaults to ../local.db
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Docs at `/api/docs`. Migrations (see `src/app/db/migrate.py`) apply automatically on startup —
this is safe to run against the pre-existing `local.db` (it gets stamped, not recreated) or a
fresh empty database.

## Test / lint

```bash
uv run pytest
uv run ruff check src/ tests/
```

Tests run against an isolated in-memory SQLite database (see `tests/conftest.py`) — they never
touch `local.db`.

## Layout

Router → Service → Repository per entity (`app/creators/`, `app/users/`, `app/posts/`), following
the vendored `.agents/skills/fastapi-*` pattern. Cross-entity SQLAlchemy models live together in
`app/db/models.py` rather than split per-entity, since the schema (ported from
`src/lib/server/db/schema.ts`) is heavily interlinked — same rationale that file itself uses.
Business logic that isn't tied to one entity (the LLM client, character-card parsing) lives under
`app/services/`.
