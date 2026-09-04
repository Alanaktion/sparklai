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
  by "does it build" — it has to wait for every route above to actually be gone first, per the
  Cleanup item below.
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
  `chat/translate.ts`) for reuse once post/chat-message translation land (both landed since — see
  the dream/memory and individual-post-page entries below). `posts/[id]/+page.svelte` now calls
  these `/api/*` paths directly instead of the deleted `+server.ts` files; the page's own
  server-side `load` (`posts/[id]/+page.server.ts`, still Drizzle-backed at the time) was ported
  separately, below.
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
- **Model/style preferences**: `GET/POST /api/models`, port of `(app)/models/+server.ts` /
  `model-preferences.ts`. New `app/services/model_preferences.py` + `app/model_preferences/`
  (router/schemas) — same plain, unsigned, session (`httponly`/`samesite=lax`, no `max-age`)
  cookies as the original (`chat_model`/`sd_style`/`sd_model`, distinct from the signed
  `creator_session` auth cookie), but resolved as a pure function of the three cookie values
  instead of mutating `chat`'s/`sd`'s old module-level globals — the same shared-state bug already
  designed around in both of those modules (see their docstrings), except this was the one place
  it hadn't actually been _fixed_ yet: nothing previously threaded a resolved chat model into any
  generation call, so the cookie had zero real effect. Fixed now via `app/dependencies.py`'s new
  `ChatModelPref` (reads the `chat_model` cookie, `Depends`-injected wherever a router ends up
  calling `chat.schema_completion()`/`.completion()`/`.translate_to_english()`) threaded as an
  explicit `model=` argument through `posts/`, `users/`, `comments/`, and `chats/`'s
  service-layer generation/translation calls — mirroring how `chat.resolve_model()` already
  resolves per-call instead of from shared state. The SD side (`sd_style`/`sd_model`) is
  deliberately _not_ wired into any generation call: even in the original, every real caller
  always passes an explicit `image_style` (the LLM decides it per post/avatar), so the
  cookie-driven global `style` fallback was already dead code for every real path — the cookie
  only ever drove this endpoint's own display/preload behavior. `ModelSwitcher.svelte` (previously
  orphaned — it fetched the bare `/models` path, which nothing had wired up since the SPA cutover
  moved API paths under `/api/*`) now calls `/api/models` and matches the new `chat_models: string[]`
  response shape (was `{id: string}[]`, matching `chat.fetch_models()`'s actual return type).
- **Dream/memory**: `POST /api/users/{id}/dream`, port of `api/users/[id]/dream/+server.ts` /
  `$lib/server/dream.ts` (both deleted — nothing else referenced either). Prompt-building split
  into a pure `app/services/dream.py` (`build_dream_prompt()` + the `DREAM_SYSTEM` text), the same
  test-without-a-database split `app/services/conversations.py` used; the DB-touching half
  (fetching the user's most recent posts/comments/chats, calling the LLM, writing `memory` back)
  is `UserService.dream()` in `app/users/service.py`. Ownership-gated the same way as `PATCH`/
  `DELETE /api/users/{id}` (401 if logged out, 403 if the requesting creator doesn't own the AI
  user), and takes the same `ChatModelPref`-resolved `model=` the other generation endpoints now
  do. `vite.config.ts`'s dev proxy no longer needs its `/api/users/*/dream` bypass — that was the
  last unported path under `/api`, so the whole `bypass` option is gone too.
- **Individual post page**: `GET /api/posts/{id}` (the whole page bundle: post + author + comments
  - the author's own gallery images/media + the requesting creator's own active AI users, in one
    call — port of `posts/[id]/+page.server.ts`'s Drizzle loader), `PATCH`/`DELETE /api/posts/{id}`
    (port of `posts/[id]/+server.ts` — the original blindly `.set()` the whole PATCH body onto the
    row with no field allowlist and silently no-opped on a missing id; now a named `PostUpdate`
    schema, `exclude_unset=True`, and a 404 for both verbs on a missing post, matching every other
    resource's PATCH/DELETE in this API), `POST /api/posts/{id}/translate` (port of
    `posts/[id]/translate/+server.ts`, same `chat.translate_to_english()` the comments pass added),
    `POST /api/posts/{id}/media` (port of `posts/[id]/media/+server.ts`'s audio/video upload). All
    four SvelteKit source files deleted, along with `$lib/server/chat/translate.ts` (now fully dead —
    this was its last caller) and the two vitest files that only covered these routes
    (`src/tests/posts.test.ts`, `src/tests/media.test.ts`; their still-relevant cases had already
    been noted as moved to `backend/tests/` in earlier passes). `PostDetailResponse` (the bundle's
    nested post) reuses `CommentResponse`/`CommentUserResponse` from `app/comments/schemas.py` for
    its `comments`/`user` fields rather than importing from `app/users/schemas.py`, which would have
    created an import cycle (`users/schemas.py` already imports `PostResponse` from here). The page's
    own `posts/[id]/+page.server.ts` load became a universal `posts/[id]/+page.ts`, same pattern as
    the chat/users pages; `ImagePicker.svelte`/`MediaPicker.svelte`/`Post.svelte`'s fetch calls moved
    from the bare `/posts/{id}` paths to `/api/posts/{id}`, dropping the `resolve()` wrapper on the
    fetch ones per the precedent set in the SD pass (kept on the plain `<a href>` navigation links,
    which are legitimate `resolve()` uses).

- **Cleanup**: deleted `src/lib/server/**`, `hooks.server.ts`, and `src/app.d.ts`'s `Locals.creator`
  (nothing referenced any of them — confirmed via grep before deleting, and `pnpm check`/`pnpm
test` after). Introduced `src/lib/types.ts`, frontend-owned response types replacing the
  Drizzle-inferred `*Type` aliases that used to live in the deleted schema file (mirrors the
  backend's Pydantic response schemas' fields, not the raw DB columns — binary `data` columns
  never appear here since the API never serializes those into JSON). Also deleted the vitest
  suite under `src/tests/` and `vitest.config.ts`: every remaining test there exercised
  SvelteKit server code that no longer exists; equivalent coverage already lives in
  `backend/tests/`.
  Dropped `drizzle-orm`, `@libsql/client`, `sharp`, `openai`, `drizzle-kit`,
  `@types/better-sqlite3`, and (once the adapter switch below landed) `@sveltejs/adapter-node`
  from `package.json`, along with the `db:push`/`db:migrate`/`db:studio`/`pin:reset`/`test`/
  `test:watch` scripts and `drizzle.config.ts`/`drizzle.test.config.ts`. Ported
  `scripts/reset-pin.mjs` to `backend/scripts/reset_pin.py` (reuses `app.security.pin.hash_pin`
  instead of reimplementing PBKDF2, so hash-format compatibility is guaranteed by construction).
  Switched `svelte.config.js` from `@sveltejs/adapter-node` to `@sveltejs/adapter-static`
  (`fallback: 'index.html'`) — safe by the time this landed, since `find src/routes -name
'+server.ts'` was empty; verified the resulting build is a genuine SPA shell (not another
  silent-discard — there was nothing left to discard) by actually running it behind the FastAPI
  backend against a `local.db` copy: `/`, deep links, real API data, a real 404 for an unmatched
  `/api/*` path, and real static-asset content-types all checked out.
  Rewrote `Dockerfile` as a multi-stage build (Node/pnpm to build the SPA, Python/uv for the
  backend, final image just the backend + built SPA as siblings) — one process on port 8000
  instead of SvelteKit's Node server on 3000, no separate database-init step (migrations already
  apply on startup). Updated `docker-compose.yml`/`docker-compose.prod.yml` to match (new port,
  `DATABASE_URL` scheme, a Python-based healthcheck instead of the old Node one-liner) and
  re-added a root `.env.docker.example` (removed earlier in this same cleanup since it described
  the old server's env vars) with the same variable names `backend/.env.example` uses but
  Docker-network-aware defaults. Verified by actually building and running the image against a
  `local.db` copy.

## Migration complete

Every domain from the original plan has an `/api/*` equivalent, the SvelteKit server is gone, and
the frontend is a static SPA served by FastAPI. `src/lib/server/**`, `hooks.server.ts`,
Drizzle/libSQL/sharp, and the old Node-server Docker setup are all gone. There's no "not done yet"
list left — day-to-day work from here is normal feature development against `backend/`, following
the vendored `.agents/skills/fastapi-*` pattern (Router → Service → Repository) documented at the
top of this file, not further migration.

## Running it

- Backend: `cd backend && uv sync --extra dev && uv run uvicorn app.main:app --reload --port
8000`. Tests: `cd backend && uv run pytest`. Lint: `uv run ruff check src/ tests/`.
- Frontend: `pnpm run dev` (proxies `/api/*` to `http://127.0.0.1:8000` by default — override with
  `BACKEND_URL`; see `vite.config.ts`). Type-check: `pnpm run check`. Lint: `pnpm run lint`.
- Production: a single container, FastAPI serving both `/api/*` and the built SPA — see
  `Dockerfile`/`docker-compose.yml`/`README.md`'s Docker Deployment section. No reverse proxy or
  second Node process needed any more.
