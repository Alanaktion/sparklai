import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.api.router import api_router
from app.config import settings
from app.database import engine
from app.db.migrate import apply_migrations
from app.exception_handlers import register_exception_handlers
from app.spa import SPAStaticFiles

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Applying database migrations")
    await asyncio.to_thread(apply_migrations)

    yield

    await engine.dispose()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api")

    # A catch-all mounted at "/" (below, for the SPA fallback) matches *any* unmatched path,
    # including under /api — without this, a typo'd or removed API route would silently 200 with
    # the SPA shell instead of a real 404. Must be registered after api_router so real API routes
    # still take precedence, but before the static mount so it wins the fallback race.
    @app.api_route("/api/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api_404(full_path: str) -> None:
        raise HTTPException(status_code=404, detail="Not Found")

    # Serve the built Svelte SPA, with a fallback to index.html for client-side routes (see
    # app/spa.py). Only mounted if the build output actually exists, so
    # `uv run uvicorn app.main:app` still works standalone in dev before `pnpm build` has run —
    # the frontend is served by `vite dev` instead in that case.
    static_dir = Path(settings.static_dir)
    if not static_dir.is_absolute():
        static_dir = Path(__file__).resolve().parents[2] / static_dir
    if static_dir.is_dir():
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")
    else:
        logger.info("No static build at %s — not mounting the SPA (dev mode?)", static_dir)

    return app


app = create_app()
