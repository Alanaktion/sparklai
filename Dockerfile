# syntax=docker/dockerfile:1

# ---- Stage 1: build the static Svelte SPA ----
FROM node:lts-slim AS frontend-build
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

# ---- Stage 2: install the FastAPI backend ----
FROM python:3.13-slim AS backend-build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app/backend
COPY backend/ .
RUN uv sync --frozen --no-dev

# ---- Final runtime image: FastAPI serves both the API and the built SPA ----
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=backend-build /app/backend /app/backend
# Lands at /app/build, a sibling of /app/backend — matches Settings.static_dir's default
# ("../build", resolved relative to backend/src/app/main.py) without needing an env override.
COPY --from=frontend-build /app/build /app/build

# Default DB location; override to point elsewhere if not using the /data volume below.
ENV DATABASE_URL="sqlite+aiosqlite:////data/local.db"

RUN mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser
WORKDIR /app/backend

EXPOSE 8000
# Migrations apply automatically on startup (app.db.migrate, run from main.py's lifespan) —
# no separate init step needed, unlike the old `pnpm run db:push`.
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
