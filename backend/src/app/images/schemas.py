from app.core.schemas import BaseSchema


class ImageUpdate(BaseSchema):
    params: dict | None = None
    blur: bool | None = None
    type: str | None = None
