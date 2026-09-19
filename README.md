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
- Front end: **Svelte** (separate app)
- **pydantic-settings** for configuration
- **pytest** + **ruff** for tests and linting

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Quickstart

```bash
uv sync                                  # install dependencies
cp .env.example .env                     # adjust as needed
uv run alembic upgrade head              # create/update the database schema
uv run fastapi dev                       # serve on http://127.0.0.1:8000
```

`uv run sparklchat` runs the same server with auto-reload.

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>

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
uv run pytest                            # run the test suite
uv run ruff check .                      # lint
uv run ruff format .                     # format

uv run alembic revision --autogenerate -m "describe change"   # new migration
uv run alembic upgrade head                                   # apply migrations
uv run alembic downgrade -1                                   # step back one
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
src/sparklchat/
  api/                       HTTP routers (`/api` prefix), auth deps, health checks
  models/                    SQLModel table models + request/response schemas
  services/                  Business logic (security, settings, ...)
  static/                    Static assets
  templates/                 Jinja2 templates
  cli.py                     `sparklchat` console entry point
  config.py                  Settings and package paths
  db.py                      Async engine, session dependency, schema helpers
  main.py                    App factory and server-rendered routes
tests/                       pytest suite
```

## Configuration

Settings are read from the environment and an optional `.env` file. See
[`.env.example`](.env.example) for the available keys. Change `SECRET_KEY`
before exposing the app to anyone else — it signs auth tokens and will encrypt
provider API keys at rest.
