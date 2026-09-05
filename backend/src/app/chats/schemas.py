from app.core.schemas import BaseSchema


class ChatImageResponse(BaseSchema):
    id: int
    blur: bool


class ChatMessageResponse(BaseSchema):
    id: int
    user_id: int
    image_id: int | None = None
    role: str
    body: str
    body_en: str | None = None
    created_at: str | None = None
    image: ChatImageResponse | None = None


class ChatMessageCreate(BaseSchema):
    message: str


class AdditionalPromptResponse(BaseSchema):
    additional_prompt: str


class AdditionalPromptUpdate(BaseSchema):
    additional_prompt: str = ""


class TranslateResponse(BaseSchema):
    body_en: str


class ConversationPreviewItem(BaseSchema):
    id: int
    body: str


class ConversationPreviewResponse(BaseSchema):
    """One entry in the `/chat` sidebar's per-user conversation preview list."""

    id: int
    name: str
    image_id: int | None = None
    chats: list[ConversationPreviewItem]
