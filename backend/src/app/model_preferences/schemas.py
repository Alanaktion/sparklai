from app.core.schemas import BaseSchema
from app.services.sd.types import SDModel


class ModelPreferencesUpdate(BaseSchema):
    """All fields optional and default-omitted: only keys actually present in the request body are
    applied (`model_dump(exclude_unset=True)` in the router), matching the original's `'chat_model'
    in body` presence checks — sending `{"chat_model": null}` clears the cookie, while omitting the
    key entirely leaves it untouched."""

    chat_model: str | None = None
    sd_style: str | None = None
    sd_model: str | None = None


class ModelPreferencesResponse(BaseSchema):
    chat_models: list[str]
    chat_model: str
    sd_backend: str
    sd_model: str
    sd_models: list[SDModel]
    sd_style: str
    sd_styles: list[str]
    sd_supports_model_selection: bool
