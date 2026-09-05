from app.comments.schemas import CommentResponse, CommentUserResponse
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


class PostUpdate(BaseSchema):
    """The only two fields any caller ever PATCHes: `ImagePicker.svelte`/`MediaPicker.svelte`
    setting or clearing `image_id`/`media_id`."""

    image_id: int | None = None
    media_id: int | None = None


class PostDetailResponse(PostResponse):
    """`PostResponse` plus the individual post page's extra bundle fields — the post's full
    author (reusing `CommentUserResponse`'s `id`/`name`/`image_id`, all the page's `Post.svelte`/
    `Avatar.svelte` actually read) and its comments (each with their own commenter, same shape
    `POST /api/posts/{id}/comments` already returns)."""

    user: CommentUserResponse
    comments: list[CommentResponse]


class PostBundleResponse(BaseSchema):
    """The whole individual post page bundle in one call. `images`/`media` are the post's
    author's own gallery (for `ImagePicker`/`MediaPicker`); `users` is the requesting creator's
    own active AI users (for the "reply as" dropdown) — both empty for a logged-out visitor."""

    id: str
    post: PostDetailResponse
    images: list[PostImageResponse]
    media: list[PostMediaResponse]
    users: list[CommentUserResponse]


class PostMediaUploadResponse(BaseSchema):
    media: PostMediaResponse
