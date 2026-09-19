# Plan: FastAPI Roleplay Chat Application

A plan/todo document for building a FastAPI-based web app for chatting with AI-backed roleplay characters using Character Card V2 (with V1 backward compatibility).

---

## 1. Project Overview

**Goal:** A self-hosted web application where users can log in, upload/create roleplay characters (Character Card V1 + V2), configure one or more AI API providers, and hold multiple independent chat sessions per character.

**Tech Stack (suggested):**
- **Backend:** FastAPI + Uvicorn, SQLModel/SQLAlchemy + Alembic, Pydantic v2
- **DB:** SQLite (dev) / PostgreSQL (prod)
- **Auth:** `fastapi-users` or hand-rolled JWT + `passlib[bcrypt]`
- **Frontend:** Jinja2 + HTMX/Alpine.js (or a separate SPA later)
- **LLM clients:** `httpx` (OpenAI-compatible, Anthropic, OpenRouter, KoboldCpp, Ollama, etc.)
- **Token counting:** `tiktoken` (approximate), pluggable
- **Tests:** `pytest`, `httpx.AsyncClient`

**Deviations adopted during implementation:**
- Layout is the uv `src/` layout (`src/sparklchat/…`) instead of a top-level `app/` package.
- Auth uses `PyJWT` + the `bcrypt` library directly (`passlib` is unmaintained).
- Front end is a separate SvelteKit SPA (`frontend/`, static adapter) served by FastAPI; no Jinja2/HTMX.
- `character_book` is stored inline in `characters.card_json`; no separate `character_books`/`lorebook_entries` tables (per §2.2's "or stored inline").
- Provider API keys are encrypted with Fernet, keyed by `ENCRYPTION_KEY` or derived from `SECRET_KEY`.
- World books (§4.4) are not implemented; only the character book is injected, toggled per session.
- Boxes below describe **API/service capability**; UI items in §6 are ticked only where the Svelte app in `frontend/` actually covers them. Still open: tag filters, chat export, world books, and theme switching.

---

## 2. Data Model

### 2.1 Core tables

| Table | Purpose |
|---|---|
| `users` | id, email, hashed_password, created_at, is_active |
| `providers` | id, user_id, name, base_url, api_key (encrypted), model, provider_type, extra_params JSON |
| `characters` | id, user_id (nullable for bundled), **raw V1/V2 JSON blob**, name, avatar_path, created_at, updated_at, source (`v1`/`v2`) |
| `character_books` | Extracted from `data.character_book` for querying (or stored inline — see §5) |
| `lorebook_entries` | One row per `entries[]` (keys, content, enabled, insertion_order, priority, etc.) |
| `chat_sessions` | id, user_id, character_id, provider_id, title, system_prompt_override, post_history_override, created_at |
| `messages` | id, session_id, role, content, created_at, token_count, is_greeting, swipe_index, metadata JSON |
| `greeting_swipes` | session_id, character_id, current_index (which alternate greeting is active) |
| `user_settings` | user_id, default_system_prompt, default_ujb, default_provider_id |

### 2.2 Character Card storage strategy

**Store the entire canonical JSON as-is** in `characters.card_json`, plus a few denormalized columns (`name`, `spec_version`) for listing/sorting. Rationale:

- Guarantees round-trip fidelity per spec: *"Character editors MUST NOT destroy unknown key-value pairs when importing and exporting"*.
- The `extensions` object at card level and inside every book entry can hold arbitrary keys — a rigid schema would fight this.
- `data.character_book` is extracted into normalized tables for prompt-time queries, but the source of truth stays in `card_json`.

---

## 3. Character Card V1/V2 Support Checklist

Every field from the spec must be handled:

### 3.1 Detection & parsing
- [x] Detect V1 vs V2 by presence of `spec == "chara_card_v2"` (fallback: presence of `data` key).
- [x] Wrap V1 cards into V2 shape on import (nest V1 fields under `data`, fill defaults: `creator_notes=""`, `system_prompt=""`, `post_history_instructions=""`, `alternate_greetings=[]`, `tags=[]`, `creator=""`, `character_version=""`, `extensions={}`).
- [x] Validate `spec_version == "2.0"` on V2.
- [x] On export, offer V1 (un-nested) or V2 depending on user choice.

### 3.2 Top-level V2 fields
- [x] `spec`, `spec_version` — read/write, validated.
- [x] `data.name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example` — used in prompt assembly.

### 3.3 V2 additions
- [x] `creator_notes` — **never** injected into prompt; shown in a dedicated "About" panel on character page (spec: *SHOULD be very discoverable*).
- [x] `system_prompt` — replaces global system prompt when non-empty; support `{{original}}` placeholder substitution.
- [x] `post_history_instructions` — replaces UJB/jailbreak when non-empty; support `{{original}}`.
- [x] `alternate_greetings: string[]` — **swipes** on first message. UI must show a swipe control on the greeting; each swipe starts a fresh branch or replaces the greeting in the current session (see §6.4).
- [x] `character_book` — full support (see §4).
- [ ] `tags: string[]` — case-insensitive filter/search, never sent to model.
- [x] `creator` — display only.
- [ ] `character_version` — display + sort.
- [x] `extensions: {}` — preserved, namespaced on write, never destroyed.

### 3.4 Avatar
- [x] Cards typically ship as PNG with embedded JSON in `tEXt` chunk (`chara` for V1, `ccv3`/`chara` for V2). Implement PNG tEXt extractor + writer so users can upload `.png` cards directly, and download their character as PNG.

---

## 4. Character Book (Lorebook) Support

Implement the full `CharacterBook` typing.

### 4.1 Fields
- [x] `name?`, `description?` — display only.
- [x] `scan_depth?` — how many recent messages to scan for keys (default: 4–8).
- [x] `token_budget?` — max tokens for lorebook content per request.
- [x] `recursive_scanning?: bool` — allow matched entry content to trigger other entries. Implement with a bounded iteration (e.g. max 3 passes) to avoid infinite loops.
- [x] `extensions: {}` — preserved.
- [x] `entries: []`.

### 4.2 Entry fields
- [x] `keys: string[]` — primary trigger keys.
- [x] `secondary_keys?: string[]` — used only when `selective == true`.
- [x] `selective?: bool` — if true, require match from **both** `keys` and `secondary_keys`.
- [x] `constant?: bool` — always inserted within budget.
- [x] `content: string` — injected text.
- [x] `enabled: bool`.
- [x] `insertion_order: number` — **lower = inserted higher** (earlier in prompt). Sort ascending.
- [x] `case_sensitive?: bool` — default false.
- [x] `priority?: number` — lower = discarded first when `token_budget` exceeded.
- [x] `position?: 'before_char' | 'after_char'` — placement relative to character definitions.
- [x] `id?`, `comment?`, `name?` — not used for prompt engineering; preserved and shown in editor.
- [x] `extensions: {}` — preserved per entry.

### 4.3 Matching algorithm (prompt-time)
1. Scan last `scan_depth` messages for each enabled entry's `keys` (respecting `case_sensitive`).
2. If `selective`, also require a `secondary_keys` hit.
3. Include `constant` entries unconditionally.
4. Sort by `insertion_order` ascending.
5. If total tokens > `token_budget`, drop by `priority` ascending (lower first) until within budget.
6. If `recursive_scanning`, re-scan entry contents for further triggers (bounded).
7. Split into `before_char` and `after_char` buckets and inject accordingly.

### 4.4 World book stacking
- [ ] Support a user-level "World Info" book.
- [ ] Character book **takes full precedence** over world book (spec: *SHOULD*). Resolve key collisions in favor of character book.
- [x] Character book is **on by default**; user can toggle per session.

---

## 5. Prompt Assembly

A single `PromptBuilder` service that produces the final message array sent to the provider.

Order (typical, matching SillyTavern conventions):

1. **System prompt** — character `system_prompt` (with `{{original}}` resolved) if non-empty, else user's global system prompt, else internal fallback.
2. **Character definition block** — `name`, `description`, `personality`, `scenario`.
3. **`before_char` lorebook entries** (per §4.3).
4. **Character definition continued / post-char** — `after_char` lorebook entries.
5. **`mes_example`** — formatted few-shot examples.
6. **Chat history** — prior messages, truncated to context window.
7. **Post-history instructions** — character `post_history_instructions` (with `{{original}}`) if non-empty, else user's UJB/jailbreak, else fallback.

Checklist:
- [x] Token counting via `tiktoken` (or per-provider tokenizer) with a configurable reserve.
- [x] Context-window truncation: drop oldest non-greeting messages first.
- [x] `{{original}}` substitution helper used in both `system_prompt` and `post_history_instructions`.
- [x] `creator_notes`, `tags`, `creator`, `character_version`, and `comment`/`id`/`name` book-entry fields are **never** sent to the model.

---

## 6. Features

### 6.1 Auth
- [x] Register / login / logout (JWT or session cookie).
- [x] Password hashing with bcrypt.
- [x] Per-user data isolation on every route.

### 6.2 Provider settings
- [x] CRUD for providers: `name`, `type` (OpenAI-compatible / Anthropic / Ollama / KoboldCpp / custom), `base_url`, `api_key`, `model`, `temperature`, `max_tokens`, `top_p`, extra JSON.
- [x] Encrypt API keys at rest (Fernet with a server key).
- [x] "Test connection" endpoint.
- [x] Set a default provider; override per session.
- [x] Streaming responses (SSE) in the chat UI.

### 6.3 Character management
- [x] Upload PNG card (extract embedded JSON + avatar).
- [x] Upload JSON card (V1 or V2).
- [x] Create from scratch in a form covering **every** V2 field.
- [x] Edit existing character (all fields, including `extensions` and book entries).
- [x] Export as V2 JSON, V1 JSON, or PNG.
- [ ] List/search/filter by `tags` (case-insensitive), `creator`, `character_version`.
- [x] Delete character (cascade sessions or block if in use — configurable).
- [x] Character detail page showing `creator_notes` (per spec: "at least one paragraph SHOULD be displayed").

### 6.4 Chat sessions
- [x] Multiple sessions per character per user.
- [x] Session title (auto from first message, editable).
- [x] Per-session provider override.
- [ ] Per-session toggle for character book / world book.
- [x] **Greeting swipes:** on session start, show `first_mes` as greeting. A swipe control cycles through `alternate_greetings`. Changing the swipe **replaces** the greeting message (and optionally branches a new session — expose as a setting).
- [x] Message swipes (regenerate last AI reply, keep N alternatives, swipe between them). Stored in `messages.metadata` or a `message_swipes` table.
- [x] Edit / delete messages.
- [x] Message roles: `system`, `user`, `assistant`.
- [x] Stop generation mid-stream.
- [ ] Export chat as JSON / Markdown.

### 6.5 UI
- [x] Sidebar: characters list, sessions per character.
- [x] Chat pane: message bubbles, swipe arrows, edit, regenerate.
- [x] Character editor: tabs for Identity / Prompting / Lorebook / Extensions / Raw JSON.
- [ ] Settings: providers, default system prompt, default UJB, theme.
- [x] Character book editor: table of entries with all fields, enable/disable toggle, drag-to-reorder `insertion_order`.

---

## 7. API Surface (draft)

```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
GET    /me

GET    /providers
POST   /providers
PATCH  /providers/{id}
DELETE /providers/{id}
POST   /providers/{id}/test

GET    /characters
POST   /characters                  # JSON body (V1 or V2)
POST   /characters/upload           # multipart PNG/JSON
GET    /characters/{id}
PATCH  /characters/{id}
DELETE /characters/{id}
GET    /characters/{id}/export?format=v1|v2|png

GET    /characters/{id}/sessions
POST   /characters/{id}/sessions
GET    /sessions/{id}
PATCH  /sessions/{id}
DELETE /sessions/{id}
GET    /sessions/{id}/messages
POST   /sessions/{id}/messages      # send user message
POST   /sessions/{id}/messages/stream  # SSE
POST   /sessions/{id}/regenerate
POST   /sessions/{id}/greeting/swipe   # {direction: "next"|"prev"}

GET    /settings
PATCH  /settings
```

---

## 8. Milestones / Todo

### M0 — Scaffolding
- [x] FastAPI project layout (`app/`, `app/api`, `app/models`, `app/services`, `app/templates`).
- [x] DB + Alembic setup, base models.
- [x] Config via `pydantic-settings` (`.env`).

### M1 — Auth & Users
- [x] Register/login/logout, JWT/session.
- [x] `user_settings` table + defaults endpoint.

### M2 — Character Card Core
- [x] Pydantic models for `TavernCardV1`, `TavernCardV2`, `CharacterBook`, book entries.
- [x] V1→V2 upconverter; strict validation; round-trip test.
- [x] PNG tEXt read/write.
- [x] CRUD endpoints + storage of raw JSON.

### M3 — Character Editor UI
- [x] Form covering every V2 field.
- [x] Raw JSON tab with validation.
- [x] Lorebook editor (all entry fields).
- [x] `extensions` editor (namespaced key/value).

### M4 — Providers
- [x] Provider CRUD + encryption.
- [x] OpenAI-compatible client, Anthropic client, Ollama client.
- [x] Streaming via SSE (provider clients + `POST /api/providers/{id}/complete/stream`).

### M5 — Prompt Builder
- [x] `{{original}}` substitution.
- [x] System prompt / post-history override logic.
- [x] Lorebook matching (§4.3) with token budget + priority + recursive scan.
- [x] before_char / after_char placement.
- [x] Unit tests for matching, budget, precedence, case sensitivity.

### M6 — Chat
- [x] Session CRUD.
- [x] Message send/stream/regenerate.
- [x] Greeting swipes from `alternate_greetings`.
- [x] Message swipes.
- [x] Edit/delete messages.

### M7 — Polish
- [x] Import/export (V1 JSON, V2 JSON, PNG).
- [ ] Tag filtering/search.
- [ ] Chat export.
- [x] Tests: card round-trip, lorebook, prompt assembly, API.

### M8 — Optional
- [ ] Multi-user sharing / public characters.
- [ ] Group chats (multiple characters).
- [ ] TTS/STT hooks via `extensions`.

---

## 9. Key Correctness Invariants (from the spec)

These must be enforced by tests:

1. Unknown keys in `extensions` (card-level, book-level, entry-level) survive import→export unchanged.
2. `creator_notes`, `tags`, `creator`, `character_version` never appear in prompts.
3. `system_prompt` / `post_history_instructions` replace the corresponding global settings by default; empty string falls back to user/internal.
4. `{{original}}` resolves to the frontend's would-be default.
5. Character book is on by default and takes precedence over the world book.
6. `alternate_greetings` are exposed as swipes on the first message.
7. `selective` entries require both `keys` and `secondary_keys`; otherwise `secondary_keys` is ignored.
8. `insertion_order` ascending = inserted higher; `priority` ascending = discarded first.
9. `position` places entry before or after character definitions.
10. V1 cards upconvert cleanly and re-export to V1 on request.
