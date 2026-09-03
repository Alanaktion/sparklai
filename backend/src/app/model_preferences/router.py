from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from app.model_preferences.schemas import ModelPreferencesResponse, ModelPreferencesUpdate
from app.services import model_preferences

router = APIRouter(prefix="/models", tags=["model-preferences"])

ChatModelCookie = Annotated[str | None, Cookie(alias=model_preferences.CHAT_MODEL_COOKIE)]
SdStyleCookie = Annotated[str | None, Cookie(alias=model_preferences.SD_STYLE_COOKIE)]
SdModelCookie = Annotated[str | None, Cookie(alias=model_preferences.SD_MODEL_COOKIE)]


@router.get("", response_model=ModelPreferencesResponse)
async def get_model_preferences(
    chat_model: ChatModelCookie = None,
    sd_style: SdStyleCookie = None,
    sd_model: SdModelCookie = None,
):
    """Port of `(app)/models/+server.ts` GET."""
    return await model_preferences.get_model_preferences(chat_model, sd_style, sd_model)


@router.post("", response_model=ModelPreferencesResponse)
async def update_model_preferences(
    data: ModelPreferencesUpdate,
    response: Response,
    chat_model: ChatModelCookie = None,
    sd_style: SdStyleCookie = None,
    sd_model: SdModelCookie = None,
):
    """Port of `(app)/models/+server.ts` POST."""
    updates = data.model_dump(exclude_unset=True)

    if "chat_model" in updates:
        chat_model = model_preferences.set_chat_model_cookie(response, updates["chat_model"])

    if "sd_style" in updates:
        sd_style = model_preferences.set_sd_style_cookie(response, updates["sd_style"])
        model_preferences.clear_sd_model_cookie(response)
        sd_model = None

    if "sd_model" in updates:
        sd_model = model_preferences.set_sd_model_cookie(response, updates["sd_model"])

    return await model_preferences.get_model_preferences(chat_model, sd_style, sd_model)
