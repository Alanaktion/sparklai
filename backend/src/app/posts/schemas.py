from app.core.schemas import BaseSchema


class PostImageResponse(BaseSchema):
    id: int
    params: dict | None = None
    blur: bool


class PostMediaResponse(BaseSchema):
    id: int
    type: str


class PostResponse(BaseSchema):
    id: int
    user_id: int
    image_id: int | None = None
    media_id: int | None = None
    body: str
    body_en: str | None = None
    created_at: str | None = None
    image: PostImageResponse | None = None
    media: PostMediaResponse | None = None


class PostsListResponse(BaseSchema):
    posts: list[PostResponse]
    hasMore: bool


class PostImageUploadResponse(BaseSchema):
    image: PostImageResponse
