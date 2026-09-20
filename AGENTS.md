# CLAUDE.md

Sparkl Chat: a self-hosted roleplay chat app for AI-backed characters using
Character Card V1/V2/V3 (`docs/`). FastAPI backend + SvelteKit SPA, talking only
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
  - `cards.py` — V1/V2/V3 card parsing/validation/normalization, format
    conversion, and V2/V3 export.
  - `png.py` — reads/writes the `chara`/`ccv3` `tEXt` chunk in avatar PNGs
    (`ccv3` wins when both are present) and reads `chara-ext-asset_:` asset
    chunks, without touching other image data.
  - `charx.py` — reads/writes `.charx` zips (`card.json` + binary assets).
  - `macros.py` — the spec's curly-braced syntaxes (`{{char}}`, `{{random:}}`,
    `{{pick:}}`, `{{roll:}}`, `{{// }}`, `{{hidden_key:}}`, `{{comment:}}`,
    `{{reverse:}}`).
  - `decorators.py` — parses lorebook `@@…` decorator lines (and `@@@` fallback
    chains) off an entry's content.
  - `packages.py` — storage for imported CHARX/PNG card packages.
  - `prompts.py` — assembles the LLM prompt: macro substitution, system/
    post-history prompt resolution, character-book and world-book entry
    matching and truncation to a token budget, multi-character "cast" blocks.
  - `chat.py` — session/message orchestration built on `prompts.py` and the
    provider clients (send, stream, regenerate, swipe).
  - `chat_import.py` — parses an imported JSON transcript (this app's export,
    or another client's message list) into roles, bodies, and speaker names.
  - `providers/` — one client per backend (`openai.py` also serves
    `koboldcpp`/`custom`, `anthropic.py`, `ollama.py`); `base.py` defines the
    common interface. Anthropic has no system role, so `chat.py`/the client
    lifts system content into the top-level `system` field.
  - `crypto.py` — Fernet encryption for provider API keys at rest.
  - `lorebook.py` — character-book / world-book entry matching logic shared by
    `prompts.py`, including V3 `use_regex` keys, decorator conditions, and
    `@@depth` routing into the chat log.
  - `tokens.py` — tiktoken-or-heuristic token counting (`TOKENIZER` setting).
  - `images.py` — best-effort Pillow encode of an uploaded image into a
downscaled WebP display variant (`to_webp`, returns `None` for anything it
cannot read).
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

`GET /api/sessions` lists the user's sessions across *all* characters (newest
activity first, joined to the primary character's name/avatar and a one-line
preview of the latest message) — it backs the dashboard, unlike the
per-character `GET /api/characters/{id}/sessions`.

### Character cards

Cards are stored as the canonical card JSON in whichever envelope they arrived
in (the whole JSON blob is the source of truth; `name`/`spec_version` columns are
denormalized only for listing/sorting). Import accepts V1, V2, and V3 and
normalizes V1 into V2 shape; `source` tracks which one it was, so export can
losslessly un-nest a V1 card again (including unknown top-level V1 keys and
`extensions` at card/book/entry level). V3 cards keep V3, and `?format=v3`
upgrades a V1/V2 card by filling the V3 defaults. Validation is strict about
types and `spec`, lenient about field *presence* (real cards omit spec-mandated
fields constantly); a non-`2.0` V2 `spec_version` is rejected with 422, while a
newer V3 `spec_version` imports with a warning (`CharacterDetail.warnings`).

V3 additions beyond the card fields: `use_regex` lorebook keys, `@@…` decorators
(`lorebook.py` + `prompts.py`), `nickname` for `{{char}}`, `group_only_greetings`
(offered only in group chats), `assets` (served via
`GET /api/characters/{id}/assets/{path}` out of the stored package), and
`creation_date`/`modification_date` stamping. `Character.package_path` holds the
imported CHARX/PNG package so assets round-trip on export.

`POST /api/characters/upload` takes a repeatable `files` field, so several cards
import in one request; each file is handled independently and returns its own
`CharacterUploadResult` (`character` or `error`), and a bad file never discards
the rest of the batch. An uploaded avatar is stored twice: `avatar_path` keeps
the original bytes (what `?format=png` embeds) and `avatar_webp_path` holds the
downscaled WebP copy (`images.py`) that `GET .../avatar` serves, so pages never
fetch the full-size original.

Per-session lorebook state (`ChatSession.lorebook_state`) records how often each
entry has matched, which is what `@@keep_activate_after_match` /
`@@dont_activate_after_match` read.

`CharacterSummary.last_message_at` is viewer-relative (the requester's newest
message in any session with that character) and is only filled in by
`GET /api/characters`, which resolves it for the whole page in one grouped query;
everywhere else it is null.

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

- `routes/+page.svelte` — the dashboard at `/`, the default view for signed-in
  users: recent chats (`GET /api/sessions`) and recently updated characters
  (showing each character's `last_message_at`), plus a "Continue last chat"
  shortcut to the newest session and a one-click "New chat" per character.
  Signed-out visitors go to `/login`.
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
- Avatars and CHARX assets are fetched through authenticated
  `/api/.../avatar` / `/api/.../assets/{path}` endpoints and rendered as blob
  URLs (`lib/avatars.ts`) — never a bare `<img src>`, since the endpoints
  require a bearer token.
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
tiktoken's BPE data, and redirects `AVATAR_DIR`/`PACKAGE_DIR` to tmp paths. Use
`registered_user`/`auth_headers`/`login_as` fixtures for authenticated
requests instead of hand-rolling registration/login in each test. `v1_card`/
`v2_card`/`v3_card` provide sample cards.
