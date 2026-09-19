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
| POST | `/api/characters` | Create from a V1 or V2 card (JSON body) |
| POST | `/api/characters/upload` | Import a PNG card or JSON file (multipart `file`) |
| GET | `/api/characters` | List your characters (`q`, `limit`, `offset`) |
| GET | `/api/characters/{id}` | Character detail, including the canonical card |
| PATCH | `/api/characters/{id}` | Replace the card (`{"card": {...}}`) |
| DELETE | `/api/characters/{id}` | Delete the character and its avatar |
| GET | `/api/characters/{id}/avatar` | The character's avatar PNG |
| GET | `/api/characters/{id}/export` | Export as `?format=v1`, `v2`, or `png` |
| GET | `/api/health` | Liveness |
| GET | `/api/health/ready` | Readiness (checks the database) |

Emails are stored lowercased, so logins are case-insensitive. Passwords must be
8+ characters and at most 72 bytes (bcrypt's limit).

In Swagger UI, use the **Authorize** button to exercise authenticated routes.

## Character cards

Cards are accepted as either **V1** (flat, six fields) or **V2** (`spec`,
`spec_version`, `data`). Import always produces the canonical V2 form; the
`source` column records whether the card arrived as `v1` or `v2`, and
`GET .../export?format=v1` un-nests it again on request.

Fidelity rules, straight from the spec:

- The whole canonical card JSON is stored verbatim and is the source of truth;
  `name` and `spec_version` are denormalized purely for listing and sorting.
- Unknown keys survive a round trip — both `extensions` (card, book, and entry
  level) and unrecognised top-level keys. Unknown top-level keys from a V1 card
  ride along on the V2 card so a V1 export stays lossless.
- `character_book` entries support every documented field, including
  `selective`/`secondary_keys`, `constant`, `position`, `insertion_order`,
  `priority`, and `case_sensitive`.

Validation is strict about *types* and about the `spec`, but lenient about field
*presence*, because real-world cards routinely omit fields the spec calls
mandatory. Unsupported specs (`chara_card_v3`) and `spec_version` values other
than `2.0` are rejected with a 422 and a clear message.

PNG cards embed their JSON base64-encoded in a `tEXt` chunk. Import reads the
`chara` chunk, falling back to `ccv3`; export writes `chara`. Only that chunk is
touched, so other PNG metadata is preserved byte-for-byte. Exporting a character
that has no avatar uses a 1×1 transparent placeholder image.

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
  models/                    SQLModel tables, card models, request/response schemas
  services/                  Card parsing, PNG tEXt I/O, security, avatars
  cli.py                     `sparklchat` console entry point
  config.py                  Settings, package paths, frontend build location
  db.py                      Async engine, session dependency, schema helpers
  main.py                    App factory, API routing, SPA serving
data/                        Local uploads (avatars); gitignored
tests/                       pytest suite
```

## Configuration

Settings are read from the environment and an optional `.env` file. See
[`.env.example`](.env.example) for the available keys. Change `SECRET_KEY`
before exposing the app to anyone else — it signs auth tokens and will encrypt
provider API keys at rest.
