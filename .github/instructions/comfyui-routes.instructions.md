---
description: This file provides a comprehensive reference for the routes exposed by the ComfyUI server, particularly those defined in `PromptServer` within `server.py`. It covers route sources, behaviors, request/response formats, and special considerations.
applyTo: 'src/lib/server/sd/*.ts'
---

# ComfyUI Server Route Reference

This document describes routes exposed by the ComfyUI server, centered on `PromptServer` in `server.py`.

## Scope and registration model

The server registers routes from multiple sources:

- `PromptServer.__init__` local route handlers (`self.routes`)
- Route providers attached in `PromptServer.add_routes()`:
  - `UserManager` (+ `AppSettings`)
  - `ModelFileManager`
  - `CustomNodeManager`
  - `SubgraphManager`
  - `NodeReplaceManager`
- Internal sub-app: `self.app.add_subapp('/internal', self.internal_routes.get_app())`
- Asset routes: `register_assets_routes(self.app, ...)` from `app/assets/api/routes.py`
- Static routes (`/`, `/extensions/...`, `/templates`, `/docs`)

### Important prefix behavior

All non-static routes in `self.routes` are registered twice:

1. Original path (for backward compatibility)
2. `/api`-prefixed alias

Alias rule:

- Alias path = `/api` + original path
- Example: `/prompt` is also available at `/api/prompt`
- Example: `/api/jobs` is also available at `/api/api/jobs` (because `/api/jobs` is itself in `self.routes`)

This duplication does **not** apply to:

- Internal sub-app routes (`/internal/...`)
- Asset routes in `app/assets/api/routes.py` (they are already mounted directly on the app)
- Static routes

## Middleware and cross-cutting behavior

Configured in `PromptServer.__init__`:

- `cache_control` (always)
- `deprecation_warning` (always)
- `compress_body` (if `--enable-compress-response-body`)
- Either:
  - CORS middleware (if `--enable-cors-header`), or
  - origin/host loopback protection middleware
- `create_block_external_middleware` (if `--disable-api-nodes`)
- manager middleware (if `--enable-manager`)

Other notes:

- Maximum request body size is controlled by `--max-upload-size` (MB), passed to `aiohttp.web.Application(client_max_size=...)`.
- Some routes behave differently in multi-user mode (`--multi-user`) by requiring/using header `comfy-user`.

## PromptServer core routes (highest priority)

All routes below are available at both original and `/api`-prefixed alias unless explicitly noted.

### `GET /ws` (WebSocket)

Purpose:

- Establishes a realtime websocket connection for queue and execution events.

Request:

- Query:
  - `clientId` (optional): reuse existing session ID

Behavior:

- On connect, server sends `status` event with queue info and assigned `sid`.
- If reconnecting the currently executing client, server may also send `executing` event.
- First text message may be feature negotiation payload:
  - `{ "type": "feature_flags", "data": { ...client flags... } }`
- Server stores client feature flags and replies with `feature_flags` event carrying server feature set.

Response:

- HTTP upgrade to websocket.

---

### `GET /`

Purpose:

- Serves frontend `index.html` from resolved web root.

Response:

- `200` HTML file response.
- Adds anti-cache headers:
  - `Cache-Control: no-store, must-revalidate`
  - `Pragma: no-cache`
  - `Expires: 0`

---

### `GET /embeddings`

Purpose:

- Lists embedding file names (without extensions).

Response:

- `200` JSON array of strings.

---

### `GET /models`

Purpose:

- Lists registered model folder types.

Response:

- `200` JSON array of model type keys.

---

### `GET /models/{folder}`

Purpose:

- Lists model files for one model folder type.

Path params:

- `folder`: model folder key

Response:

- `200` JSON array of file names
- `404` if `folder` is unknown

---

### `GET /extensions`

Purpose:

- Lists frontend extension JS files from:
  - frontend web root `extensions/**/*.js`
  - loaded custom extension dirs (`nodes.EXTENSION_WEB_DIRS`)

Response:

- `200` JSON array of URL paths.

---

### `POST /upload/image`

Purpose:

- Uploads image to input/output/temp area.

Request:

- Multipart form fields:
  - `image` (required file)
  - `type` (optional: `input` | `output` | `temp`, default `input`)
  - `subfolder` (optional)
  - `overwrite` (optional truthy: `true`/`1`)

Behavior:

- Prevents path traversal (`commonpath` checks).
- If overwrite is false/missing and file exists, appends ` (n)` unless file hash is identical (duplicate suppression).
- If assets are enabled, attempts to register uploaded file and adds `asset` block to response.

Response:

- `200` JSON:
  - `{ "name", "subfolder", "type" }`
  - optional `asset` object (`id`, `name`, `asset_hash`, `size`, `mime_type`, `tags`)
- `400` for invalid input/path

---

### `POST /upload/mask`

Purpose:

- Uploads a mask and applies its alpha channel to an existing target image.

Request:

- Multipart form fields include:
  - `image` mask file
  - `original_ref` JSON string with `filename`, optional `type`, optional `subfolder`

Behavior:

- Resolves original file safely.
- Loads original RGBA image and mask RGBA image.
- Replaces original alpha with mask alpha and writes output via upload flow.

Response:

- Same base response/status behavior as `/upload/image`.

---

### `GET /view`

Purpose:

- Serves image file content or transformed preview channels.

Request query:

- `filename` (required)
- If filename starts with `blake3:`, resolves via assets (`resolve_hash_to_path`)
- Otherwise supports:
  - `type` (default `output`)
  - `subfolder` (optional)
- Optional transforms:
  - `preview=<format>[;quality]` where format usually `webp`/`jpeg`
  - `channel=rgba|rgb|a`

Behavior:

- Enforces path traversal protection for non-hash mode.
- `channel=rgb`: returns PNG RGB merge.
- `channel=a`: returns alpha-only PNG.
- default channel: serves file with content type guess or resolved asset content type.
- Dangerous mime types are forced to `application/octet-stream`.

Response:

- `200` binary file/image response (varies by mode)
- `400`, `403`, `404` for invalid/forbidden/missing cases

---

### `GET /view_metadata/{folder_name}`

Purpose:

- Reads `.safetensors` metadata header and returns `__metadata__` content.

Path params:

- `folder_name`

Query:

- `filename` (must end with `.safetensors`)

Response:

- `200` JSON object (`__metadata__`)
- `404` for invalid/missing/non-safetensors/no metadata

---

### `GET /system_stats`

Purpose:

- Returns runtime system/device stats.

Response:

- `200` JSON with:
  - `system`: OS, RAM, ComfyUI version, frontend/templates versions, Python/PyTorch versions, argv, etc.
  - `devices`: list with current torch device stats (`vram_total`, `vram_free`, etc.)

---

### `GET /features`

Purpose:

- Returns server feature flags.

Response:

- `200` JSON object from `feature_flags.get_server_features()`

---

### `GET /prompt`

Purpose:

- Returns queue summary info.

Response:

- `200` JSON:
  - `{ "exec_info": { "queue_remaining": <int> } }`

---

### `GET /object_info`

Purpose:

- Returns metadata/schema for all node classes.

Behavior:

- Starts asset seeder for roots `models/input/output`.
- Iterates `nodes.NODE_CLASS_MAPPINGS` and builds info per node.

Response:

- `200` JSON object keyed by node class.

---

### `GET /object_info/{node_class}`

Purpose:

- Returns metadata/schema for one node class (if exists).

Response:

- `200` JSON object; empty object if unknown node class.

---

### `GET /api/jobs`

Purpose:

- Lists jobs with filtering/sorting/pagination.

Query params:

- `status`: comma-separated `pending,in_progress,completed,failed`
- `workflow_id`
- `sort_by`: `created_at` (default) or `execution_duration`
- `sort_order`: `asc` or `desc` (default)
- `limit`: positive integer (optional)
- `offset`: non-negative integer (default `0`, negatives normalized to `0`)

Response:

- `200` JSON:
  - `{ "jobs": [...], "pagination": { "offset", "limit", "total", "has_more" } }`
- `400` on invalid filters/sort/pagination values

Alias note:

- Because of auto-prefixing, this route is also available at `/api/api/jobs`.

---

### `GET /api/jobs/{job_id}`

Purpose:

- Returns a single job by ID.

Path params:

- `job_id`

Response:

- `200` JSON job object
- `400` if missing id
- `404` if not found

Alias note:

- Also available at `/api/api/jobs/{job_id}`.

---

### `GET /history`

Purpose:

- Returns execution history.

Query:

- `max_items` (optional int)
- `offset` (optional int, default `-1`)

Response:

- `200` JSON history structure from prompt queue.

---

### `GET /history/{prompt_id}`

Purpose:

- Returns history for one prompt id.

Response:

- `200` JSON history entry/list from prompt queue.

---

### `GET /queue`

Purpose:

- Returns running and pending queue snapshots with sensitive tuple data removed.

Response:

- `200` JSON:
  - `queue_running`
  - `queue_pending`

---

### `POST /prompt`

Purpose:

- Validates and enqueues a workflow prompt.

Request JSON (main fields):

- `prompt` (required)
- `prompt_id` (optional, auto-generated if absent)
- `number` (optional)
- `front` (optional bool; negates generated number if true)
- `partial_execution_targets` (optional)
- `extra_data` (optional object)
- `client_id` (optional, copied into `extra_data.client_id`)

Behavior:

- Runs `trigger_on_prompt` hooks.
- Applies registered node replacements.
- Validates via `execution.validate_prompt(...)`.
- Splits sensitive keys from `extra_data` into separate `sensitive` map.
- Enqueues tuple `(number, prompt_id, prompt, extra_data, outputs_to_execute, sensitive)`.

Response:

- `200` JSON on success:
  - `{ "prompt_id", "number", "node_errors" }`
- `400` JSON on invalid prompt or missing `prompt`:
  - invalid prompt: `{ "error", "node_errors" }`
  - no prompt: `{ "error": {type/message/details/...}, "node_errors": {} }`

---

### `POST /queue`

Purpose:

- Mutates queue state.

Request JSON:

- `clear` (optional bool): clears pending queue
- `delete` (optional array of prompt IDs): removes matching queue entries

Response:

- `200` empty response

---

### `POST /interrupt`

Purpose:

- Interrupts processing globally or for a specific running prompt.

Request JSON:

- optional `prompt_id`

Behavior:

- If `prompt_id` is provided, interrupt only if that prompt is currently running.
- Otherwise interrupts globally.

Response:

- `200` empty response

---

### `POST /free`

Purpose:

- Sets memory/model release flags consumed by queue executor.

Request JSON:

- `unload_models` (optional bool)
- `free_memory` (optional bool)

Response:

- `200` empty response

---

### `POST /history`

Purpose:

- Mutates history state.

Request JSON:

- `clear` (optional bool): wipe history
- `delete` (optional array of prompt IDs): delete selected history entries

Response:

- `200` empty response

## User and settings routes

Defined in `app/user_manager.py` and `app/app_settings.py`, attached to `self.routes` (therefore each also has `/api` alias).

### Settings

- `GET /settings`: returns full settings object for request user.
- `GET /settings/{id}`: returns setting value or `null` if missing.
- `POST /settings`: merges JSON body into existing settings; returns `200`.
- `POST /settings/{id}`: sets one setting to JSON body value; returns `200`.

### Users

- `GET /users`:
  - multi-user mode: `{ "storage": "server", "users": {user_id: display_name} }`
  - single-user mode: `{ "storage": "server", "migrated": <bool> }`
- `POST /users`:
  - body: `{ "username": "..." }`
  - returns new user_id string
  - `400` on duplicate/invalid username

### User data

- `GET /userdata`:
  - query: `dir` (required), optional `recurse`, `full_info`, `split`
  - returns list of file paths or rich file info
  - `400` missing dir, `403` invalid path, `404` not found
- `GET /v2/userdata`:
  - query: `path` (optional)
  - recursive structured listing of files/directories with metadata
  - includes sorting (directories first, then files)
- `GET /userdata/{file}`:
  - serves requested file
  - `400`/`403`/`404` on invalid path state
- `POST /userdata/{file}`:
  - body: raw file bytes
  - query: `overwrite` (default true), `full_info` (default false)
  - returns relative path or full file info
  - `409` when overwrite disabled and target exists
- `DELETE /userdata/{file}`:
  - deletes file, returns `204`
- `POST /userdata/{file}/move/{dest}`:
  - query: `overwrite`, `full_info`
  - moves/renames file and returns destination path/info

## Model manager routes

Defined in `app/model_manager.py` (with `/api` aliases via prefixing).

- `GET /experiment/models`
  - returns model folder descriptors: `{ name, folders[] }[]`
- `GET /experiment/models/{folder}`
  - returns full model file list with metadata (`name`, `pathIndex`, `modified`, `created`, `size`)
  - `404` unknown folder
- `GET /experiment/models/preview/{folder}/{path_index}/{filename:.*}`
  - returns model preview image as `image/webp`
  - `404` on invalid folder/index/path/no preview

## Custom node routes

Defined in `app/custom_node_manager.py` (with `/api` aliases via prefixing).

- `GET /workflow_templates`
  - returns map: custom node package name -> list of workflow template names
- `GET /i18n`
  - returns merged translation dictionary from custom node locale files

Also registers static workflow template routes directly on app (not duplicated):

- `GET /api/workflow_templates/{module_name}/...` (static files)

## Subgraph routes

Defined in `app/subgraph_manager.py` (with `/api` aliases via prefixing).

- `GET /global_subgraphs`
  - returns all discovered subgraph entries (custom nodes + blueprints) without raw `data`
- `GET /global_subgraphs/{id}`
  - returns one subgraph entry, including loaded raw `data` content

## Node replacement route

Defined in `app/node_replace_manager.py` (with `/api` alias via prefixing).

- `GET /node_replacements`
  - returns serialized node replacement registry

## Asset routes

Defined in `app/assets/api/routes.py`, mounted directly on app.

Feature gating:

- If assets are disabled, guarded routes return:
  - `503` with code `SERVICE_DISABLED`

Routes:

- `HEAD /api/assets/hash/{hash}`
  - checks asset content hash existence
  - `200` if exists, `404` if not, `400` for invalid hash format

- `GET /api/assets`
  - paginated/filterable asset list
  - query includes tags/name/metadata filters, sort/order, limit/offset
  - returns `{ assets, total, has_more }`

- `GET /api/assets/{id}`
  - returns one asset summary/detail
  - `404` if missing

- `GET /api/assets/{id}/content`
  - streams file content
  - query: `disposition=inline|attachment` (default attachment)
  - sets safe `Content-Disposition` and `X-Content-Type-Options: nosniff`

- `POST /api/assets/from-hash`
  - creates asset reference from existing content hash
  - returns `201` with `created_new` flag

- `POST /api/assets`
  - multipart upload/create route
  - supports fast path when provided hash already exists
  - returns `201` when new content created, else `200`

- `PUT /api/assets/{id}`
  - updates asset metadata/name/preview reference
  - returns updated asset object

- `DELETE /api/assets/{id}`
  - deletes asset reference; optional query `delete_content`
  - `204` on success

- `GET /api/tags`
  - lists tags with usage counts and pagination

- `POST /api/assets/{id}/tags`
  - body with tags to add
  - returns `{ added, already_present, total_tags }`

- `DELETE /api/assets/{id}/tags`
  - body with tags to remove
  - returns `{ removed, not_present, total_tags }`

- `GET /api/assets/tags/refine`
  - returns tag histogram for filtered asset subset

- `POST /api/assets/seed`
  - starts assets seeding for roots
  - query `wait=true` for synchronous completion
  - statuses: `202` started, `409` already running, `200` completed (wait mode)

- `GET /api/assets/seed/status`
  - returns current seeding state/progress/errors

- `POST /api/assets/seed/cancel`
  - requests cancellation (`cancelling` or `idle`)

- `POST /api/assets/prune`
  - marks out-of-root assets as missing (soft prune)
  - `200` completed, `409` if scan currently running

## Static routes

Configured in `PromptServer.add_routes()`:

- `/extensions/{name}/...` (for each entry in `nodes.EXTENSION_WEB_DIRS`)
- `/templates/...`
  - legacy static mount when template version < `0.3.0`, else dynamic GET handler
- `/docs/...` (embedded docs, when available)
- `/...` frontend static root (`self.web_root`)
