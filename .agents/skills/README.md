# Vendored skills

The `comfyui-*`, `svelte-code-writer`, and `tailwind-design-system` skills in this directory were
installed by an external skill-management CLI (referenced as `openclaw` in their frontmatter) that
isn't available in every environment this repo is worked in.

The `fastapi-*` skills were added the same way conceptually, but hand-vendored: fetched directly
from their upstream GitHub source ([`agusmdev/burntop`](https://github.com/agusmdev/burntop)
`.claude/skills/`) and copied in verbatim, because the real skill CLI wasn't reachable from the
environment that added them. Their `computedHash` in `skills-lock.json` is a plain `sha256` of the
`SKILL.md` file content (marked `"manuallyVendored": true`), not whatever hash scheme the real CLI
uses for its other entries — don't expect it to verify against that tool.

They document a FastAPI + async SQLAlchemy 2.0 + async Alembic stack with a 3-layer
(Router → Service → Repository) architecture, originally written against PostgreSQL/asyncpg with
UUID primary keys. This repo's backend adapts the same layering and Alembic setup to SQLite
(`aiosqlite`, batch-mode migrations, integer autoincrement primary keys matching the pre-existing
schema) rather than following the Postgres/UUID specifics literally. See
`fastapi-backend-overview/SKILL.md` for the index of the rest of the pack.
