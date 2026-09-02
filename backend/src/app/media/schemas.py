from app.core.schemas import BaseSchema


class MediaUpdate(BaseSchema):
    params: dict | None = None
    type: str | None = None
