# CLAUDE.md

Sparkl Chat: a self-hosted roleplay chat app for AI-backed characters using
Character Card V1/V2 (`docs/`). FastAPI backend + SvelteKit SPA, talking only
over `/api`.

## Commands

Backend (from repo root, `uv`-managed):

```bash
uv sync                                  # install/update deps
uv run alembic upgrade head              # apply migrations (do this after pulling schema changes)
uv run fastapi dev                       # dev server on :8000 (auto-reload)
uv run pytest                            # full backend test suite
uv run pytest tests/test_cards.py        # single file
uv run pytest tests/test_cards.py::test_name -x   # single test
uv run ruff check .                      # lint
uv run ruff format .                     # format
uv run alembic revision --autogenerate -m "describe change"   # new migration
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev            # :5173, proxies /api to :8000 — run alongside `fastapi dev`
npm run check          # svelte-kit sync + svelte-check (TypeScript)
npm test               # vitest (markdown parser + rich-text renderer)
npm run build          # production SPA build -> frontend/build
```

There is no single top-level "run everything" command — backend and frontend
are two processes in dev. In production, `uv run fastapi run` serves both:
FastAPI hosts `frontend/build` (see routing rules below) once it exists.

A Svelte-specific skill (`.agents/skills/svelte-code-writer`) wraps
`npx @sveltejs/mcp` for docs lookup and an autofixer — run the autofixer before
finalizing any `.svelte`/`.svelte.ts` change.

## Architecture

### Backend layout (`src/sparklchat/`)

- `api/` — FastAPI routers, one per resource (`auth`, `characters`, `chat`,
  `providers`, `settings`, `users`, `health`), plus `deps.py` for auth/session
  dependencies and `access.py` for ownership checks. All mounted under `/api`
  via `router.py`.
- `models/` — SQLModel tables. This is the schema source of truth for Alembic;
  **new models must be imported from `models/__init__.py`** or autogenerate
  won't see them.
- `services/` — the actual logic, kept independent of FastAPI:
  - `cards.py` — V1/V2 card parsing/validation/normalization.
  - `png.py` — reads/writes the `chara`/`ccv3` `tEXt` chunk in avatar PNGs
    without touching other image data.
  - `prompts.py` — assembles the LLM prompt: macro substitution, system/
    post-history prompt resolution, character-book and world-book entry
    matching and truncation to a token budget, multi-character "cast" blocks.
  - `chat.py` — session/message orchestration built on `prompts.py` and the
    provider clients (send, stream, regenerate, swipe).
  - `providers/` — one client per backend (`openai.py` also serves
    `koboldcpp`/`custom`, `anthropic.py`, `ollama.py`); `base.py` defines the
    common interface. Anthropic has no system role, so `chat.py`/the client
    lifts system content into the top-level `system` field.
  - `crypto.py` — Fernet encryption for provider API keys at rest.
  - `lorebook.py` — character-book / world-book entry matching logic shared by
    `prompts.py`.
  - `tokens.py` — tiktoken-or-heuristic token counting (`TOKENIZER` setting).
  - `downloads.py`, `avatars.py`, `security.py`, `user_settings.py` — smaller
    single-purpose helpers.
- `config.py` — `pydantic-settings` `Settings`; also resolves the frontend
  build directory and package paths.
- `db.py` — async engine/session setup, SQLite FK enforcement, schema helpers.
- `main.py` — app factory (`create_app`); wires `/api` routing plus SPA
  fallback serving.

### Chat / group chat model

A `ChatSession` has one primary `character_id` (owns the greeting, title
fallback, and the character's session-list membership) plus a
`SessionCharacter` join table holding the *ordered full cast*, including the
primary — so the cast is always readable without falling back to
`chat_sessions.character_id`. `Message.speaker_id` records which character
sent an assistant line (null = user/system, or a legacy row implying the
primary character). `prompts.py`'s `CastMember`/`_member_block` build one
prompt block per non-primary cast member.

`Message.meta` (named `meta`, not `metadata`, because SQLAlchemy's declarative
base reserves that name) holds swipe alternatives for both regular messages
and the seeded greeting.

Streaming endpoints (`.../messages/stream`, `.../regenerate/stream`) emit SSE
events `user` → `delta`* → `message` → `done` (or `error`); if the stream fails
mid-way, whatever text arrived is still persisted before the `error` event.

### Character cards

Cards are stored as canonical V2 JSON (the whole JSON blob is the source of
truth; `name`/`spec_version` columns are denormalized only for listing/
sorting). Import accepts V1 or V2 and always normalizes to V2; `source` tracks
which one it was so `?format=v1` export can losslessly un-nest it again,
including unknown top-level V1 keys and `extensions` at card/book/entry level.
Validation is strict about types and `spec`, lenient about field *presence*
(real cards omit spec-mandated fields constantly); `chara_card_v3` and
non-`2.0` `spec_version` are rejected with 422.

Voice hooks (TTS/STT) are card-declared, not app config: `extensions.sparklchat`
on the card (see `models/hooks.py`) opts a character into browser Web Speech
API behavior. This block is read leniently (bad/missing data silently
degrades to disabled) and is never written back by prompt assembly.

### Providers

One `Provider` row = one endpoint (type, base URL, model, sampling settings,
optional encrypted API key). `provider_type` `koboldcpp`/`custom` reuse the
OpenAI-compatible client; `openai`/`anthropic`/`ollama` each have a real one.
`extra_params` merges into the request body for provider-specific fields, but
never overrides the dedicated columns or the request envelope
(`model`/`messages`/`stream`). API keys are Fernet-encrypted using
`ENCRYPTION_KEY` (falls back to being derived from `SECRET_KEY` — set
`ENCRYPTION_KEY` explicitly before you have keys worth keeping, since rotating
`SECRET_KEY` would otherwise strand them) and are never returned by the API
(`has_api_key` only).

### SPA serving / routing (`main.py`)

FastAPI serves `frontend/build` when present (`FRONTEND_DIST_DIR` overrides
the path). Rules, in order: `/api/*` always wins; an unknown `/api/*` path
returns JSON 404 (never the SPA shell); any other path returns the SPA shell
*only* for navigation requests (`Accept: text/html`) so client-side routes
survive a hard refresh, while a missing asset under a non-navigation request
still 404s so broken `fetch()` calls are loud, not silently swallowed. Tests
exercise this via the `spa_client`/`spa_dist` fixtures in `tests/conftest.py`,
which fake a build output rather than requiring a real `npm run build`.

### Frontend (`frontend/src/`)

- `lib/api.ts` — typed client for every `/api` endpoint; this is the contract
  boundary the backend must keep in sync with.
- `lib/markdown.ts` — a small roleplay-specific Markdown-like parser (see
  README's syntax table for supported conventions: `*action*` italics,
  `**bold**`, blockquotes, fenced/backtick code, escaped `\*literal\*`, and
  preserved single newlines instead of paragraph-breaking them). It returns
  data, not HTML — `RichText.svelte` renders it as text nodes, so message
  content cannot inject markup. Don't reintroduce raw HTML rendering here.
  Covered by `markdown.test.ts` / `RichText.test.ts`, including an XSS
  regression test.
- `lib/auth.svelte.ts`, `lib/theme.svelte.ts` — Svelte 5 rune-based state
  (`.svelte.ts` modules, not plain `.ts`).
- `lib/speech.ts` — wraps the browser's Web Speech API per the card's
  `extensions.sparklchat` hooks (see above); no server involvement.
- Avatars are fetched through the authenticated `/api/.../avatar` endpoint and
  rendered as a blob URL (`lib/avatars.ts`) — never a bare `<img src>`, since
  the endpoint requires a bearer token.
- `routes/+layout.ts` disables SSR — this is a pure client-rendered SPA.

Svelte 5 is in use throughout (runes, not stores-first patterns) — check the
`svelte-code-writer` skill and run its autofixer for any `.svelte` /
`.svelte.ts` work.

## Database / migrations

Alembic (`alembic/`) owns the schema; `DATABASE_URL` (env/`.env`) is the single
source for both the app and Alembic — no separate Alembic config needed.
SQLite (default, via `aiosqlite`) and PostgreSQL (`asyncpg`) are both
supported; SQLite foreign-key enforcement is turned on per-connection
automatically. After adding/changing a model, register it in
`models/__init__.py`, then `uv run alembic revision --autogenerate -m "..."`
and review the generated migration before committing — autogenerate is a
starting point, not ground truth.

## Testing conventions

Every test gets a throwaway SQLite file via the `engine`/`app`/`client`
fixtures in `tests/conftest.py`, which override the `get_session` FastAPI
dependency — tests never touch the dev `sparklchat.db`. `isolated_uploads` is
autouse and forces `TOKENIZER=heuristic` so tests don't hit the network for
tiktoken's BPE data, and redirects `AVATAR_DIR` to a tmp path. Use
`registered_user`/`auth_headers`/`login_as` fixtures for authenticated
requests instead of hand-rolling registration/login in each test.
