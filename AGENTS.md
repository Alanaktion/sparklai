# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SparklAI is a fake social media site: an LLM ("Creators" author AI "Users" who post, comment, and
DM) plus Stable Diffusion generate all of the site's users, posts, images, and DMs. It's two apps
in one repo:

- **Frontend**: SvelteKit (Svelte 5, TypeScript, Tailwind v4) built as a pure static SPA via
  `adapter-static`, source in `src/`.
- **Backend**: FastAPI (Python, `backend/`), SQLAlchemy 2.0 async + Alembic, SQLite (`local.db` at
  repo root) as the data store, and its own `openai`-client integration for chat/LLM completions
  plus an HTTP client for Stable Diffusion (Automatic1111 or ComfyUI).

The backend serves both `/api/*` and the built SPA from one FastAPI process/container (see
`backend/src/app/main.py` and `Dockerfile`) — there is no separate Node server in production. In
dev, `vite dev` serves the frontend and proxies `/api` to FastAPI (see `vite.config.ts`).

The project was migrated off a SvelteKit+Drizzle/libSQL backend to this FastAPI backend (see the
`feat: switch frontend to static SPA via adapter-static` / `chore: drop Drizzle/libSQL/sharp/openai`
commits). **`.github/copilot-instructions.md` in this repo describes the old Drizzle/`db:push`
architecture and is stale — do not follow it.**

## Commands

### Frontend (repo root)

```bash
pnpm install
pnpm run dev            # vite dev server, proxies /api/* to FastAPI on :8000 (override with BACKEND_URL)
pnpm run build           # production build -> build/ (served by FastAPI)
pnpm run check           # svelte-kit sync + svelte-check (TypeScript/Svelte types)
pnpm run lint            # prettier --check . && eslint .
pnpm run format          # prettier --write .
```

There is no frontend test suite/script (no `test` script in `package.json`) — note that
`.github/workflows/ci.yml` runs `pnpm run test`, which does not currently exist as a script.
Backend tests (below) are the only automated tests in the repo.

### Backend (`backend/`)

```bash
cd backend
uv sync --extra dev
cp .env.example .env    # set SESSION_SECRET at minimum

uv run uvicorn app.main:app --reload --port 8000   # run (docs at /api/docs)
uv run pytest                                       # run all tests
uv run pytest tests/test_posts.py                   # run one test file
uv run pytest tests/test_posts.py::test_name -v     # run one test
uv run ruff check src/ tests/                       # lint
```

Migrations (`app/db/migrate.py`) apply automatically on process startup, both for `uv run
uvicorn` and for the Docker image — there's no separate migrate/init step, and it's safe to run
against the pre-existing `local.db` (gets stamped, not recreated) or an empty one. Tests run
against an isolated in-memory SQLite DB (`tests/conftest.py`) and never touch `local.db`.

### Docker

`docker compose up -d` builds the single-container deploy (FastAPI serving `/api/*` + the SPA on
port 8000); `docker-compose.prod.yml` is the production variant. See `README.md` for the full
Ollama/Stable Diffusion service setup — the LLM/SD endpoints can't use `localhost` from inside the
container (`host.docker.internal`, bundled service names, or an external API).

## Architecture

### Backend: Router → Service → Repository per entity

Each domain lives in its own package under `backend/src/app/` (`creators/`, `users/`, `posts/`,
`comments/`, `chats/`, `images/`, `image_jobs/`, `media/`, `model_preferences/`), each following
the same layering (adapted from the vendored `.agents/skills/fastapi-*` pattern — see
`backend/README.md` and `.agents/skills/README.md` for the provenance/adaptation notes):

- `router.py` — FastAPI routes, wired together in `app/api/router.py` and mounted under `/api`.
- `service.py` — business logic.
- `repository.py` — DB access.
- `schemas.py` — Pydantic request/response models. `src/lib/types.ts` on the frontend mirrors
  these response schemas by hand (not the raw DB columns — e.g. binary blob columns never appear
  there since the API never serializes them into JSON).

Cross-entity SQLAlchemy models are **not** split per-entity: they all live together in
`app/db/models.py` because the schema is heavily interlinked (see that file's docstring), on the
shared `Base` in `app/core/models.py`. Business logic not tied to one entity (LLM client,
character-card import, Stable Diffusion) lives under `app/services/` instead of an entity package.

The models intentionally mirror a pre-existing SQLite schema exactly — integer autoincrement PKs
(not the UUID style the vendored fastapi-* skills originally assumed), hard deletes, and
timestamps kept as `Text` rather than `DateTime` (they're plain `CURRENT_TIMESTAMP`-formatted
strings; mapping to `DateTime` risks a parse mismatch against existing rows). Don't "fix" these to
match the vendored skill patterns — the schema compatibility is deliberate.

A catch-all route in `app/main.py` matches any unmatched path under `/api` and returns a real 404
before the SPA static mount can swallow it as `index.html` — keep that ordering (`api_router` →
the catch-all → the SPA mount) if you touch route registration.

### Stable Diffusion backends

`app/services/sd/` supports two backends selected by `SD_BACKEND` (`automatic1111` or `comfyui`).
For ComfyUI, style-specific workflow templates in `app/services/sd/workflows/` are submitted to
ComfyUI's prompt queue with placeholders (`__MODEL__`, `__POSITIVE_PROMPT__`, `__SEED__`, etc.)
substituted in; if you replace a template, keep its `output_node_id` and placeholder structure in
sync with `app/services/sd/client.py`, or update both together.

### Frontend: static SPA, all data via `fetch('/api/...')`

`adapter-static` with `fallback: 'index.html'` (`svelte.config.js`) means every route's `load`
runs client-side (`+page.ts`/`+layout.ts`, not `+page.server.ts`) and fetches from the FastAPI
backend — there is no server-side rendering or direct DB access from the frontend anymore. Deep
links / refreshes on client-side routes are served `index.html` by FastAPI's `SPAStaticFiles`
(`backend/src/app/spa.py`).

Routes are grouped under `src/routes/(app)/` (main feed, users, posts, settings — behind the
active "Creator" context) and `src/routes/chat/` (messenger). The active Creator (the
human-controlled account that "owns" a set of generated Users) is loaded once in
`src/routes/(app)/+layout.ts` from `/api/creators/me` and read elsewhere via Svelte context
(`src/lib/user-profile-context.ts`) rather than re-fetched.

### Environment config

Backend settings are a single `pydantic-settings` `Settings` class (`backend/src/app/config.py`),
env-file driven — see `backend/.env.example` for the full list (DB URL, session secret, chat
LLM endpoint/model, per-style SD model/prompt/negative-prompt triples). Frontend dev proxy target
is `BACKEND_URL` (`vite.config.ts`), separate from the backend's own env vars.
