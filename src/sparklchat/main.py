"""FastAPI application factory and server-rendered routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sparklchat.api.router import api_router
from sparklchat.config import STATIC_DIR, TEMPLATES_DIR, Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Future home of the engine warm-up / provider client pool.
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured `FastAPI` instance."""
    settings = settings or get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(api_router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    templates.env.globals["app_name"] = settings.app_name

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html")

    return app


app = create_app()
