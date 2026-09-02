# FastAPI backend migration

Tracks the move of SparklAI's backend from SvelteKit server routes (`src/lib/server/**`,
`hooks.server.ts`, `+server.ts`/`+*.server.ts` files) to a standalone FastAPI service under
`backend/`, with the Svelte app ending up as a static SPA. See the skills vendored under
`.agents/skills/fastapi-*` (from [`agusmdev/burntop`](https://github.com/agusmdev/burntop),
adapted from Postgres/UUID to this app's SQLite/integer-PK schema — see
`.agents/skills/README.md`) for the architectural pattern (Router → Service → Repository,
async SQLAlchemy 2.0, async Alembic) new domains should follow.

## Done

- **Foundation**: `backend/` FastAPI project (uv-managed), async SQLAlchemy models mirroring
  `src/lib/server/db/schema.ts` exactly (`backend/src/app/db/models.py`), Alembic migrations
  applied on startup (`backend/src/app/db/migrate.py` — stamps a pre-existing `local.db` to
  baseline instead of recreating it; see that module's docstring).
- **Auth/creators**: signup, login, logout, `GET /api/creators/me`, `PATCH /api/creators/me`
  (settings). Signed session cookie (`itsdangerous`) instead of the old raw creator-id cookie.
  PBKDF2 PIN hashing ported 1:1 (`backend/src/app/security/pin.py`) — existing password hashes
  keep working.
- **Home feed vertical slice**: `GET/POST /api/posts` (cursor pagination + random-user post
  generation), `GET/POST /api/users` (list + AI-generated create), `POST /api/import-character`
  (character card import). Chat/LLM client ported to `backend/src/app/services/chat.py` — no
  module-level mutable `model` global (see that file's docstring for the bug this fixes).
- **Frontend serving**: FastAPI serves the built SPA directly, including client-side-route
  fallback (`backend/src/app/spa.py`'s `SPAStaticFiles`, plus an explicit `/api/{full_path:path}`
  404 catch-all in `main.py` so an unmatched API path can't fall through to the SPA shell). The
  original SvelteKit route _paths_ (`/users/123`, `/settings`, etc.) are unchanged — only the
  backend API paths moved under `/api/*`, deliberately diverging from the old bare `/posts`,
  `/users` etc. paths (those are now free for the SPA's own client-side routes to use, which they
  couldn't be under the old hybrid SvelteKit-server/page-route setup).
  **Confirmed by experiment, not just reasoned about:** temporarily switching
  `svelte.config.js` to `adapter-static` still produces a "successful" build — but it _silently
  discards every remaining `+server.ts` endpoint's code_ rather than erroring (only genuinely
  prerendered pages and the `index.html` fallback shell survive; `find build -type d` shows no
  page directories at all, everything is fallback-only). That means the cutover can't be validated
  by "does it build" — it has to wait for every item below to actually be gone, per item 4.
- **AI user profile management**: `GET /api/users/{id}` (the whole profile-page bundle: user +
  `isOwner` + posts + gallery images + relationships, in one call — port of
  `users/[id]/+layout.server.ts`), `PATCH`/`DELETE /api/users/{id}` (now enforces the requesting
  creator actually owns the AI user — the original had no server-side check at all, even though
  the edit page's own `+page.server.ts` gated on `isOwner` client-side; see `users/router.py`),
  `POST /api/users/{id}/posts` (generate post for a specific user), `POST /api/users/{id}/images`
  (bulk gallery upload, port of `image-utils.ts`'s `toWebp()` → Pillow in
  `app/services/image_utils.py`). The singular, dual-purpose `POST /api/users/{id}/image` (quick
  avatar upload _or_ SD-prompt generation) landed with the Stable Diffusion port below.
- **Binary serving**: `GET/PATCH/DELETE /api/images/{id}` and `/api/media/{id}`.
- **Comments**: `POST /api/posts/comments` (random-post/random-author AI comment, port of the
  oddly-placed `posts/comments/+server.ts`), `POST /api/posts/{id}/comments` (plain user comment —
  now takes a JSON `{message}` body instead of the original's form-urlencoded one, since the only
  caller is the frontend fetch updated alongside this),`POST /api/posts/{id}/comments/respond`
  (AI-generated reply, specific or random user), `DELETE /api/posts/{id}/comments/{comment_id}`,
  `POST /api/posts/{id}/comments/{comment_id}/translate`. New `app/comments/` entity; translation
  now lives as `chat.translate_to_english()` in `app/services/chat.py` (was
  `chat/translate.ts`) for reuse once post/chat-message translation land. `posts/[id]/+page.svelte`
  now calls these `/api/*` paths directly instead of the deleted `+server.ts` files; the page's own
  server-side `load` (`posts/[id]/+page.server.ts`, still Drizzle-backed) is untouched — see the
  gap noted below.
- **Chat/messenger**: `GET/PUT /api/users/{id}/chat/context`, `GET/POST /api/users/{id}/chat/messages`
  (create now takes JSON `{message}`, same modernization as comments — the original's
  form-urlencoded body is gone), `DELETE .../messages/{message_id}`,
  `POST .../messages/{message_id}/translate`, `POST .../chat/respond` (full persona system-prompt
  port, including relationship context and the summary-aware history partitioning),
  `POST .../chat/new-conversation` (summarizes the active segment into a marker message), and
  `GET /api/chats` (the `/chat` sidebar's conversation-preview list, port of
  `chat/+layout.server.ts`). New `app/chats/` entity; conversation-history partitioning/formatting
  ported to `app/services/conversations.py` (was `$lib/chat/conversations.ts`, a pure module —
  copied rather than shared, since the frontend still needs its own copy for
  `hasActiveConversation()`/`ChatMessage.svelte`'s summary-marker rendering) and
  `now_str()`/`format_date()` to `app/services/formatting.py` (was the two server-used exports of
  `$lib/index.ts`). Both `routes/chat/**` pages are fully converted to universal
  (`+layout.ts`/`+page.ts`) loads hitting these endpoints; `chat/[id]/+page.svelte`'s chat-history
  fetch moved from the old server-only streamed-promise pattern (`{#await data.chats}`, no SPA
  equivalent) to a plain client fetch gated by a `loadingChats` state var, per the plan. The
  pre-existing `todo.txt` item (per-pairing DM prompt overrides — currently `additional_prompt` is
  one value per AI user, not per creator/user pairing) is **not** addressed by this pass; it's
  unrelated to the migration itself and still open.
- **Stable Diffusion / image generation**: Automatic1111/ComfyUI clients ported to
  `app/services/sd/client.py` (port of `sd/index.ts` — no mutable module-level "current
  style"/"current model" default; see that file's docstring for why, and for the one deliberately
  _local_, non-shared cache it does keep). The in-memory `Map`-based job queue (`sd/jobs.ts`)
  became `app/services/sd/jobs.py`: `asyncio.create_task` per job, each with its own DB session
  (`database.async_session_factory()`, not the request's — a background task outlives the
  request), plus `recover_pending_jobs()` called from `main.py`'s startup to re-attach any
  `queued`/`processing` rows left over from a previous process. New `app/image_jobs/` entity for
  `GET /api/image-jobs` (creator's in-flight jobs) and `GET /api/image-jobs/{id}`. The dual-purpose
  `POST /api/users/{id}/image` (upload avatar directly, or queue 1-5 AI-generated ones) and
  `POST /api/posts/{id}/image` (upload directly, or queue one AI-concept-generated one via the new
  `post_image` `schema_completion` variant) landed in `users/router.py` / `posts/router.py`.
  `posts/service.py`'s `generate_post_for_user()` now actually enqueues a job when
  `response["image_generation"]` is present, instead of just logging and skipping. Not ported: the
  `SD_DEBUG_LOG` request/response file-logging hook (dev-only debugging aid, not user-facing
  behavior).
  **Also fixed while here** (found via `pnpm check`, not part of the SD port itself): deleting the
  now-fully-ported-or-dead SvelteKit routes below removed a same-shape catch-all route
  (`(app)/[id]/+server.ts`, a byte-for-byte duplicate of `image-jobs/[id]/+server.ts` at the bare
  path `/[id]`) that had been silently widening `resolve()`'s generated type enough to accept
  _any_ interpolated-string route argument — masking that a bunch of `fetch()` calls elsewhere
  (`CreatorSwitcher.svelte`, `MediaPicker.svelte`, `ImagePicker.svelte`'s image-thumbnail `src`,
  from earlier sessions of this same migration) were passing pre-built path strings to `resolve()`,
  which isn't actually valid for parameterized routes. Fixed every such call by dropping the
  `resolve()` wrapper (matching `Image.svelte`'s existing plain-string precedent — `resolve()` is
  for typed internal navigation, not arbitrary fetch targets to begin with) rather than switching
  to `resolve()`'s tuple-args form, which doesn't apply to `/api/*` paths anyway (they aren't
  SvelteKit page routes). Two of those turned out to be genuine, unrelated bugs rather than just
  type noise: `ImagePicker.svelte`'s thumbnail `src` and `MediaPicker.svelte`'s `<source>` `src`
  were both still pointing at the bare `/images/{id}` / `/media/{id}` paths deleted back in the
  "Binary serving" pass (should've been `/api/images/{id}` / `/api/media/{id}`), and
  `users/[id]/edit/+page.svelte`'s "Save Changes" button was PATCHing bare `/users/{id}` (deleted
  in the "AI user profile management" pass) instead of `/api/users/{id}` — the edit form's save
  button has been silently broken since that pass landed. All three now fixed alongside the type
  errors that surfaced them.
  Also deleted as fully dead code (zero remaining importers once the above landed):
  `src/lib/server/index.ts` (`generatePost`/`generateComment`, both long superseded — the
  home-feed and comments passes moved every caller to FastAPI already, this just hadn't been
  swept up yet) and `src/lib/server/image-utils.ts` (`toWebp`, superseded by
  `app/services/image_utils.py`).

## Not done yet — port in roughly this order

Each item: the SvelteKit source to retire, the pattern to reuse.

1. **Model/style preferences** — `(app)/models/+server.ts`. Replace
   `model-preferences.ts`'s per-request global mutation with per-request resolution (cookie/header
   read → passed as a parameter), for both chat model and SD style/model — same fix already
   applied to the chat client, and designed into `app/services/sd/client.py` from the start (see
   that file's docstring for the extension point).
2. **Dream/memory** — `api/users/[id]/dream/+server.ts`.
3. **Individual post page** — `posts/[id]/+page.server.ts` (the loader itself: post + comments +
   user + creator's other images/media/users, still on Drizzle), `posts/[id]/+server.ts`
   (PATCH/DELETE the post), `posts/[id]/translate/+server.ts` (same
   `chat.translate_to_english()` the comments pass added). `posts/[id]/media/+server.ts`
   (audio/video upload) can land with this too, or separately — it doesn't overlap with SD.
4. **Cleanup**, once nothing on the SvelteKit side references them any more:
   - Delete `src/lib/server/**`, `hooks.server.ts`, `src/app.d.ts`'s `Locals.creator`.
   - Drop `drizzle-orm`, `@libsql/client`, `sharp`, and the `db:push`/`db:migrate`/`db:studio`
     scripts from `package.json`.
   - **Only then** switch `svelte.config.js` from `@sveltejs/adapter-node` to the already-installed
     `@sveltejs/adapter-static` (`fallback: 'index.html'`, SPA mode). Not before — adapter-static
     can't serve any of the routes above; flipping early breaks everything not yet ported.
   - Update `Dockerfile`/`docker-compose*.yml` for the two-service (or single, if FastAPI serves
     the built SPA — see `backend/src/app/main.py`) deployment.

## Working during the transition

- `vite.config.ts` proxies `/api/*` to FastAPI (`http://127.0.0.1:8000` by default, override with
  `BACKEND_URL`) in dev, **except** `/api/users/*/dream` which isn't ported yet and still needs to
  hit SvelteKit's own dev server — see the `bypass` in that config for the exact rule, and update
  it as more routes move over.
- There's currently no production-equivalent of that proxy: a shared/deployed environment needs a
  reverse proxy (nginx, etc.) routing ported paths to FastAPI and everything else to the SvelteKit
  Node server until the full cutover in item 4 above.
- Run the backend with `cd backend && uv sync --extra dev && uv run uvicorn app.main:app --reload
--port 8000`. Tests: `cd backend && uv run pytest`. Lint: `uv run ruff check src/ tests/`.
