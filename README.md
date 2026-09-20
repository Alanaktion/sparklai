# Sparkl Chat

A self-hosted web app for roleplay chat with AI-backed characters, supporting
Character Card V1, V2, and V3 (see [`docs/`](docs) for the specs) and multiple
independently configured AI providers.

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
| POST | `/api/providers` | Create a provider (API key stored encrypted) |
| GET | `/api/providers` | List your providers |
| GET | `/api/providers/{id}` | Provider detail |
| PATCH | `/api/providers/{id}` | Update; `"api_key": null` clears the stored key |
| DELETE | `/api/providers/{id}` | Delete, clearing it as the default if needed |
| POST | `/api/providers/{id}/test` | Send a tiny prompt to verify the connection |
| POST | `/api/providers/{id}/complete` | One-off completion |
| POST | `/api/providers/{id}/complete/stream` | The same, streamed as Server-Sent Events |
| POST | `/api/characters` | Create from a V1, V2, or V3 card (JSON body) |
| POST | `/api/characters/upload` | Import one or more PNG cards, CHARX packages, or JSON files (repeatable multipart `files`; returns a per-file result) |
| GET | `/api/characters` | List your characters (`q`, `limit`, `offset`; rows carry the viewer's `last_message_at`) |
| GET | `/api/characters/{id}` | Character detail, including the canonical card |
| PATCH | `/api/characters/{id}` | Replace the card (`{"card": {...}}`) |
| DELETE | `/api/characters/{id}` | Delete the character and its avatar |
| GET | `/api/characters/{id}/avatar` | The character's avatar image (an optimized WebP copy when one was stored) |
| GET | `/api/characters/{id}/assets/{path}` | A binary asset from the stored CHARX package |
| GET | `/api/characters/{id}/export` | Export as `?format=v1`, `v2`, `v3`, `png`, or `charx` |
| GET | `/api/characters/{id}/sessions` | Chat sessions for this character |
| POST | `/api/characters/{id}/sessions` | Start a session (seeds the greeting) |
| POST | `/api/characters/{id}/sessions/import` | Import a JSON chat transcript as a new session (multipart `file`) |
| GET | `/api/sessions` | Your recent sessions, across all characters (dashboard) |
| GET | `/api/sessions/{id}` | Session plus its messages |
| PATCH | `/api/sessions/{id}` | Title, provider override, prompt overrides, book toggle |
| DELETE | `/api/sessions/{id}` | Delete the session and its messages |
| GET | `/api/sessions/{id}/export` | Download the transcript as `?format=json` or `markdown` |
| GET | `/api/sessions/{id}/messages` | Messages in order |
| POST | `/api/sessions/{id}/messages` | Send a message (non-streaming) |
| POST | `/api/sessions/{id}/messages/stream` | Send a message, streamed as SSE |
| PATCH | `/api/sessions/{id}/messages/{mid}` | Edit a message |
| DELETE | `/api/sessions/{id}/messages/{mid}` | Delete a message |
| POST | `/api/sessions/{id}/messages/{mid}/swipe` | Cycle message alternatives |
| POST | `/api/sessions/{id}/greeting/swipe` | Cycle the greeting alternatives |
| POST | `/api/sessions/{id}/regenerate` | New alternative for the last reply |
| POST | `/api/sessions/{id}/regenerate/stream` | The same, streamed |
| GET | `/api/health` | Liveness |
| GET | `/api/health/ready` | Readiness (checks the database) |

Emails are stored lowercased, so logins are case-insensitive. Passwords must be
8+ characters and at most 72 bytes (bcrypt's limit).

In Swagger UI, use the **Authorize** button to exercise authenticated routes.

## Character cards

Cards are accepted as **V1** (flat, six fields), **V2**, or **V3** (`spec`,
`spec_version`, `data`), from raw JSON, an uploaded PNG, or a CHARX package.
Import normalises V1 into V2 shape but otherwise keeps the format the card
arrived in: V2 cards stay V2, V3 cards stay V3. The `source` column records
`v1`, `v2`, or `v3`, and `GET .../export?format=...` converts on request —
including `format=v3`, which fills the V3 defaults for a V2/V1 card. Several
files can be imported in a single `POST /api/characters/upload`; each is handled
independently and reports its own error, so one bad file does not lose the rest.

Uploaded avatars are stored twice: the original bytes (what exports embed) and a
downscaled WebP copy that `GET .../avatar` serves to the UI.

Fidelity rules, straight from the spec:

- The whole canonical card JSON is stored verbatim and is the source of truth;
  `name` and `spec_version` are denormalized purely for listing and sorting.
- Unknown keys survive a round trip — both `extensions` (card, book, and entry
  level) and unrecognised top-level keys. Unknown top-level keys from a V1 card
  ride along on the V2 card so a V1 export stays lossless.
- `character_book` entries support every documented field, including
  `selective`/`secondary_keys`, `constant`, `position`, `insertion_order`,
  `priority`, `case_sensitive`, and the V3 `use_regex` (whose `keys` are then
  regex patterns, optionally written as `/pattern/flags`).
- V3 cards keep their `nickname`, `assets`, `source`,
  `creator_notes_multilingual`, `group_only_greetings`, `creation_date`, and
  `modification_date`. `creation_date` is filled in when a V3 card is created
  without one, and `modification_date` is refreshed on export.

Validation is strict about *types* and about the `spec`, but lenient about field
*presence*, because real-world cards routinely omit fields the spec calls
mandatory. A V3 card written to a newer `spec_version` is imported with a
warning (`warnings` on the detail response) rather than rejected, and a V2 card
whose `spec_version` is not `2.0` is rejected with a 422.

### Embedding methods

- **JSON** — the card object on its own.
- **PNG** — the JSON base64-encoded in a `tEXt` chunk: `ccv3` for V3 cards,
  `chara` for V1/V2. The spec says `ccv3` wins when a file carries both, so that
  is the read order, and a V3 export writes `ccv3`. Binary assets may also ride
  along in `chara-ext-asset_:{path}` chunks; those are read (never written) and
  preserved. Only the chunks we care about are touched, so other PNG metadata is
  preserved byte-for-byte. Exporting a character with no avatar uses a 1×1
  transparent placeholder image.
- **CHARX** — a zip with `card.json` at its root plus the card's binary assets.
  Assets are served through `/api/characters/{id}/assets/{path}` so an
  `embeded://path` asset URI works in the UI, and the package is kept on disk so
  a CHARX export round-trips losslessly. Encrypted packages and packages without
  a root `card.json` are rejected.

### Prompts and lorebooks

The V3 spec's lorebook decorators (`@@activate`, `@@dont_activate`,
`@@scan_depth`, `@@activate_only_after`/`@@activate_only_every`,
`@@keep_activate_after_match`/`@@dont_activate_after_match`, `@@is_greeting`,
`@@is_user_icon`, `@@additional_keys`/`@@exclude_keys`,
`@@ignore_on_max_context`, `@@depth`/`@@role`, and `@@position`,
`@@disable_ui_prompt`) are honoured when assembling prompts, as are the
curly-braced syntaxes (`{{char}}` uses the nickname, `{{random:}}`, `{{pick:}}`,
`{{roll:}}`, `{{// }}`, `{{hidden_key:}}`, `{{comment:}}`, `{{reverse:}}`).
Decorator lines are stripped before a lorebook entry's content reaches the
model. `@@keep_activate_after_match`/`@@dont_activate_after_match` need to know
whether an entry matched before; that count is kept per session in
`chat_sessions.lorebook_state` and refreshed on every generation.

## Providers

A provider is one endpoint to talk to: its type, base URL, model, sampling
settings, and an optional API key.

| `provider_type` | Driven by | Default base URL |
| --- | --- | --- |
| `openai` | OpenAI-compatible client | `https://api.openai.com/v1` |
| `anthropic` | Anthropic Messages API | `https://api.anthropic.com` |
| `ollama` | Ollama native `/api/chat` | `http://127.0.0.1:11434` |
| `koboldcpp` | OpenAI-compatible client | `http://127.0.0.1:5001/v1` |
| `custom` | OpenAI-compatible client | required from you |

OpenAI-compatible, Anthropic, and Ollama each have a real client; `koboldcpp`
and `custom` are served by the OpenAI-compatible one (KoboldCpp's
`/v1` chat-completions endpoint). Anthropic's API has no system role, so system
messages are lifted into the top-level `system` field and `max_tokens` is filled
in when unset, since Anthropic requires it.

`extra_params` is merged into the request body for provider-specific fields
(for example Ollama's `keep_alive`, OpenAI's `frequency_penalty`). The dedicated
columns and the request envelope (`model`, `messages`, `stream`) take precedence,
so extras cannot accidentally break a request.

**API keys are encrypted at rest** with Fernet and are never returned — the API
exposes only `has_api_key`. The key comes from `ENCRYPTION_KEY` when set, and is
otherwise derived from `SECRET_KEY`; see [`.env.example`](.env.example).

Set a default provider through `PATCH /api/settings` with `default_provider_id`.
It must reference one of your own providers, and deleting a provider that is your
default clears the reference. Per-session overrides arrive with chat sessions.

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
npm test                                 # vitest (markdown parser + renderer)
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
  models/                    SQLModel tables (users, providers, characters, chat)
  services/                  Card parsing, PNG/CHARX I/O, macros, providers, prompts
    providers/               OpenAI-compatible, Anthropic, and Ollama clients
  cli.py                     `sparklchat` console entry point
  config.py                  Settings, package paths, frontend build location
  db.py                      Async engine, session dependency, schema helpers
  main.py                    App factory, API routing, SPA serving
data/                        Local uploads (avatars, CHARX packages); gitignored
tests/                       pytest suite
```

## Chat

Starting a session seeds the character's `first_mes` as an assistant message, with
`alternate_greetings` attached as swipes; macro placeholders are resolved once at
that point, so the greeting reads naturally.

Sending a message appends the user turn, assembles the prompt, and calls the
provider — either in one shot or streamed as Server-Sent Events:

```
event: user     data {"message": Message}   the persisted user turn
 event: delta    data {"delta": "..."}       incremental assistant text
event: message  data {"message": Message}   the persisted assistant turn
event: error    data {"detail": "..."}
event: done     data {}
```

Regenerating appends a new alternative to the last assistant message and makes it
active; the previous reply stays available via the swipe endpoints, which is also
how message swipes and greeting swipes work. `messages.meta` holds the
alternatives (the column is named `meta` because SQLAlchemy reserves `metadata`).

The first user message becomes the session title unless one was set. Deleting a
character cascades to its sessions and messages; deleting a provider clears it as
the default and leaves its sessions to fall back to the new default.

If the stream fails part-way, whatever arrived is saved before the `error` event
so partial text is not lost.

### Importing transcripts

`GET /api/sessions/{id}/export?format=json|markdown` downloads a transcript, and
`POST /api/characters/{id}/sessions/import` takes one back in as a new session
for that character (multipart `file`). Two JSON shapes are understood:

- this app's own export, which carries a `session` header plus a `characters`
  cast, and
- the plain message lists other clients write, where each entry has its body
  under `msg`/`mes`/`content`/`text` and enough context to tell who spoke — a
  `role`, an `is_user` flag, or a `characterId`/`userId` speaker pair.

The path character becomes the session's primary character. A transcript that
names its other characters (as this app's export does) pulls in any of the
importing user's *own* characters with a matching name, so a group chat imports
with its speakers intact; a named speaker with no match falls back to the
primary. A `greeting` the message list left out is restored from the file (and
matched, never duplicated, when the list already includes it), and recognised
`createdAt`/`send_date`/epoch timestamps are kept — session `created_at`/
`updated_at` follow the transcript, so imported history lands where it belongs
on the dashboard.

## The Svelte app

The front end covers sign in/up, the character list (search, upload, delete),
character detail with `creator_notes` and transcript import, the chat view
(streaming, swipes, edit, delete, regenerate, provider picker, character-book
toggle), and settings (providers with a Test button, plus display name and
default prompts).

Avatars come from an authenticated endpoint, so the app fetches them with the
bearer token and renders a blob URL rather than using `<img src>` directly.

### Message formatting

Replies are rendered through a small Markdown-like parser (`src/lib/markdown.ts`)
covering the conventions roleplay text actually uses:

| Syntax | Renders as |
| --- | --- |
| `*sighs*` | italics — the action convention |
| `**Now**` | bold |
| `***both***` | bold italics |
| `_quietly_`, `__loudly__` | italics / bold (word boundaries only, so `snake_case` survives) |
| `~~gone~~` | strikethrough |
| `` `code` ``, fenced ```` ``` ```` blocks | monospace |
| `> line` | blockquote |
| `\*escaped\*` | literal characters |

Single newlines are preserved rather than treated as paragraph breaks, since
models break replies across lines far more often than they intend a new
paragraph. Dialogue in straight quotes is left as-is rather than auto-styled,
which would misfire on apostrophes and nested quotes.

The parser returns data, not HTML, and the renderer emits text nodes, so message
content can never inject markup — a test asserts that `<img onerror=…>` in a
reply renders escaped.

## Configuration

Settings are read from the environment and an optional `.env` file. See
[`.env.example`](.env.example) for the available keys. Change `SECRET_KEY`
before exposing the app to anyone else — it signs auth tokens and will encrypt
provider API keys at rest.
