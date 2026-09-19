# Sparkl Chat

A self-hosted web app for roleplay chat with AI-backed characters, supporting
Character Card V1 and V2 (see [`docs/`](docs) for the specs) and multiple
independently configured AI providers.

> Status: early scaffolding. See [`PLAN.md`](PLAN.md) for the full roadmap.

## Stack

- **FastAPI** + **Uvicorn** (async), **Pydantic v2**
- **SQLModel** on SQLAlchemy with an async engine (SQLite via `aiosqlite` in
  development; PostgreSQL via `asyncpg` in production)
- **Alembic** for schema migrations
- **JWT bearer auth** (`PyJWT`) with **bcrypt** password hashing
- **SvelteKit** single-page app (`@sveltejs/adapter-static`) built with **Vite**
  and **TypeScript**
- **pydantic-settings** for configuration
- **pytest** + **ruff** for the backend, **svelte-check** for the front end

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm (front end only)

## Quickstart (API)

```bash
uv sync                                  # install dependencies
cp .env.example .env                     # adjust as needed
uv run alembic upgrade head              # create/update the database schema
uv run fastapi dev                       # serve on http://127.0.0.1:8000
```

`uv run sparklchat` runs the same server with auto-reload.

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>

## Front end

The Svelte app lives in [`frontend/`](frontend). Either run its dev server next
to the API, or build it and let FastAPI serve it — both talk to the same `/api`
endpoints.

**Development** (two processes, one origin from the browser's perspective):

```bash
uv run fastapi dev          # API on :8000
cd frontend && npm install
npm run dev                 # app on :5173, proxies /api to :8000
```

**Production** (FastAPI hosts everything):

```bash
cd frontend && npm install && npm run build   # writes frontend/build
uv run fastapi run                            # API + SPA on :8000
```

FastAPI serves `frontend/build` when it exists (override with
`FRONTEND_DIST_DIR`). Routing rules:

- API routes under `/api` always win.
- Unknown `/api/*` paths return a JSON 404 rather than the SPA shell.
- Every other path returns the SPA, so client-side routes such as
  `/characters/5` work on a hard refresh.
- Only navigation requests (`Accept: text/html`) get the SPA shell; a missing
  asset still 404s, so broken `fetch()` calls surface loudly.

If the build directory is absent the server logs a hint and serves the API only.

## API overview

Endpoints live under `/api`. Auth uses OAuth2 bearer tokens: `POST
/api/auth/login` takes form-encoded `username` (the email) and `password`, and
returns an access token to send as `Authorization: Bearer <token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account (JSON `email` + `password`) |
| POST | `/api/auth/login` | Exchange credentials for a bearer token |
| POST | `/api/auth/logout` | No-op for stateless tokens; clients discard theirs |
| GET | `/api/me` | The authenticated user |
| GET | `/api/settings` | Per-user prompt defaults |
| PATCH | `/api/settings` | Update prompt defaults |
| GET | `/api/health` | Liveness |
| GET | `/api/health/ready` | Readiness (checks the database) |

Emails are stored lowercased, so logins are case-insensitive. Passwords must be
8+ characters and at most 72 bytes (bcrypt's limit).

In Swagger UI, use the **Authorize** button to exercise authenticated routes.

## Common tasks

```bash
uv run pytest                            # backend tests
uv run ruff check .                      # lint
uv run ruff format .                     # format

uv run alembic revision --autogenerate -m "describe change"   # new migration
uv run alembic upgrade head                                   # apply migrations
uv run alembic downgrade -1                                   # step back one

cd frontend
npm run check                            # svelte-check + TypeScript
npm run build                            # production SPA build
```

The database schema is owned by Alembic. Add new models under
`src/sparklchat/models/` and import them from `models/__init__.py` so
autogenerate can see them.

## PostgreSQL

`asyncpg` is already a dependency, so production is a URL change away:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sparklchat \
  uv run alembic upgrade head
```

Alembic reads the same `DATABASE_URL` as the app, so no other configuration is
needed. SQLite foreign-key enforcement is enabled per connection automatically.

## Project layout

```
alembic/                     Migration environment and versioned migrations
alembic.ini                  Alembic configuration (URL comes from Settings)
docs/                        Character Card V1/V2/V3 specifications
frontend/                    SvelteKit SPA (Svelte 5 + TypeScript)
  src/lib/api.ts             Typed client for the /api endpoints
  src/routes/                File-based routes (+layout.ts switches off SSR)
  vite.config.ts             Static SPA adapter + /api dev proxy
src/sparklchat/
  api/                       HTTP routers (`/api` prefix), auth deps, health checks
  models/                    SQLModel table models + request/response schemas
  services/                  Business logic (security, settings, ...)
  cli.py                     `sparklchat` console entry point
  config.py                  Settings, package paths, frontend build location
  db.py                      Async engine, session dependency, schema helpers
  main.py                    App factory, API routing, SPA serving
tests/                       pytest suite
```

## Configuration

Settings are read from the environment and an optional `.env` file. See
[`.env.example`](.env.example) for the available keys. Change `SECRET_KEY`
before exposing the app to anyone else — it signs auth tokens and will encrypt
provider API keys at rest.
