"""FastAPI application factory, API routing, and static front end serving."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from sparklchat.api.router import api_router
from sparklchat.config import Settings, get_settings

logger = logging.getLogger(__name__)

_API_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Future home of the engine warm-up / provider client pool.
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured `FastAPI` instance."""
    settings = settings or get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(api_router)
    _add_api_not_found_handler(app)
    _mount_frontend(app, settings)
    return app


def _add_api_not_found_handler(app: FastAPI) -> None:
    """Keep unknown `/api/*` requests away from the SPA fallback.

    `app.frontend()` registers a low-priority catch-all that answers navigation
    requests with `index.html`. Without this route, a browser hitting a mistyped
    API path would receive the SPA shell with a 200 instead of an API error.

    Note that any unmatched `/api/*` request reports 404, including a known path
    called with an unsupported method: FastAPI matches included routers lazily,
    so the method-mismatch (405) case cannot be detected here without relying on
    private internals.
    """

    @app.api_route("/api/{path:path}", methods=_API_METHODS, include_in_schema=False)
    async def api_not_found() -> JSONResponse:
        return JSONResponse({"detail": "Not Found"}, status_code=404)


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built Svelte SPA, when a build is present.

    API routes are matched first; everything else — including client-side deep
    links such as `/characters/5` — is served `index.html`.
    """
    dist = settings.frontend_dist_dir
    if not dist.is_dir():
        logger.warning(
            "No frontend build at %s; serving the API only. Run `npm install && "
            "npm run build` in frontend/, or use the Vite dev server.",
            dist,
        )
        return
    app.frontend("/", directory=dist, fallback="index.html", check_dir=False)


app = create_app()
