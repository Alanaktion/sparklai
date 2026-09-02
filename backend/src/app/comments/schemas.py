from app.core.schemas import BaseSchema


class CommentUserResponse(BaseSchema):
    id: int
    name: str
    image_id: int | None = None


class CommentResponse(BaseSchema):
    id: int
    post_id: int
    user_id: int | None = None
    body: str
    body_en: str | None = None
    created_at: str | None = None
    user: CommentUserResponse | None = None


class CommentCreate(BaseSchema):
    message: str


class RespondRequest(BaseSchema):
    user_id: int | None = None


class TranslateResponse(BaseSchema):
    body_en: str
