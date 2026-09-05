"""Chat model / Stable Diffusion style-model preference cookies.

These cookies are plain, unsigned, `httponly`/`samesite=lax` session cookies — no relation to the
separate signed `creator_session` auth cookie — and nothing here mutates process-wide state.
`get_model_preferences()` is a pure function of the three cookie values; `app/dependencies.py`'s
`ChatModelPref` reads the `chat_model` cookie and hands it to callers as an explicit `model=`
argument into `chat.schema_completion()`/`chat.completion()` — the same resolve-fresh-per-request
pattern `chat.resolve_model()` uses internally.

The SD side (`sd_style`/`sd_model` cookies) is intentionally *not* wired into any actual generation
call: every real caller of `sd.start_generation()`/`txt2img()` in this app always passes an
explicit `image_style` (the LLM decides it per post/avatar, see `app/services/sd/client.py`'s
docstring), so there's no code path where a cookie-driven default would ever apply — the cookie
only ever drives this preferences endpoint's own display/preload behavior, never actual output.
"""

from typing import TypedDict

from fastapi import Response

from app.services import chat
from app.services.sd import client as sd_client
from app.services.sd.types import SD_STYLE_NAMES, SDModel, SDStyle

CHAT_MODEL_COOKIE = "chat_model"
SD_STYLE_COOKIE = "sd_style"
SD_MODEL_COOKIE = "sd_model"

_DEFAULT_SD_STYLE: SDStyle = "photo"

_COOKIE_KWARGS = {"path": "/", "httponly": True, "samesite": "lax"}


class ModelPreferences(TypedDict):
    chat_models: list[str]
    chat_model: str
    sd_backend: str
    sd_model: str
    sd_models: list[SDModel]
    sd_style: str
    sd_styles: list[str]
    sd_supports_model_selection: bool


def normalize_cookie_value(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def parse_sd_style(value: str | None) -> SDStyle | None:
    if value in SD_STYLE_NAMES:
        return value  # type: ignore[return-value]
    return None


def _pick(requested: str | None, available: list[str], fallback: str) -> str:
    if requested and requested in available:
        return requested
    if fallback in available:
        return fallback
    return available[0] if available else ""


def set_chat_model_cookie(response: Response, value: str | None) -> str | None:
    """Sets (or, given a falsy value, clears) the `chat_model` cookie on `response`, returning the
    normalized value now in effect — callers should carry that value forward locally rather than
    re-reading `request.cookies`, which won't reflect a same-request write."""
    normalized = normalize_cookie_value(value)
    if not normalized:
        response.delete_cookie(CHAT_MODEL_COOKIE, path="/")
        return None
    response.set_cookie(CHAT_MODEL_COOKIE, normalized, **_COOKIE_KWARGS)
    return normalized


def set_sd_style_cookie(response: Response, value: str | None) -> SDStyle | None:
    normalized = parse_sd_style(value)
    if not normalized:
        response.delete_cookie(SD_STYLE_COOKIE, path="/")
        return None
    response.set_cookie(SD_STYLE_COOKIE, normalized, **_COOKIE_KWARGS)
    return normalized


def set_sd_model_cookie(response: Response, value: str | None) -> str | None:
    if not sd_client.supports_model_selection():
        response.delete_cookie(SD_MODEL_COOKIE, path="/")
        return None
    normalized = normalize_cookie_value(value)
    if not normalized:
        response.delete_cookie(SD_MODEL_COOKIE, path="/")
        return None
    response.set_cookie(SD_MODEL_COOKIE, normalized, **_COOKIE_KWARGS)
    return normalized


def clear_sd_model_cookie(response: Response) -> None:
    response.delete_cookie(SD_MODEL_COOKIE, path="/")


async def get_model_preferences(
    chat_model_cookie: str | None,
    sd_style_cookie: str | None,
    sd_model_cookie: str | None,
) -> ModelPreferences:
    chat_models = await chat.fetch_models()
    fallback_chat_model = await chat.resolve_model(None)
    chat_model = _pick(
        normalize_cookie_value(chat_model_cookie), chat_models, fallback_chat_model
    )

    sd_style = parse_sd_style(sd_style_cookie) or _DEFAULT_SD_STYLE
    sd_models = await sd_client.fetch_models()
    supports_model_selection = sd_client.supports_model_selection()
    if supports_model_selection:
        sd_model = _pick(
            normalize_cookie_value(sd_model_cookie),
            [m["model_name"] for m in sd_models if m.get("model_name")],
            sd_client.styles[sd_style]["model"],
        )
    else:
        sd_model = sd_client.styles[sd_style]["model"]

    return ModelPreferences(
        chat_models=chat_models,
        chat_model=chat_model,
        sd_backend=sd_client.backend,
        sd_model=sd_model,
        sd_models=sd_models,
        sd_style=sd_style,
        sd_styles=list(SD_STYLE_NAMES),
        sd_supports_model_selection=supports_model_selection,
    )
