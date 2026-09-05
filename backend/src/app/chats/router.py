from fastapi import APIRouter

from app.chats.repository import ChatRepository
from app.chats.schemas import (
    AdditionalPromptResponse,
    AdditionalPromptUpdate,
    ChatMessageCreate,
    ChatMessageResponse,
    ConversationPreviewItem,
    ConversationPreviewResponse,
    TranslateResponse,
)
from app.chats.service import ChatService
from app.dependencies import ChatModelPref, CurrentCreator, DbDep, RequireCreator

router = APIRouter(prefix="/users/{user_id}/chat", tags=["chats"])

# Mounted separately (no `/users/{user_id}` prefix) for the `/chat` sidebar's conversation list.
conversations_router = APIRouter(tags=["chats"])


def _service(db: DbDep) -> ChatService:
    return ChatService(ChatRepository(db))


@conversations_router.get("/chats", response_model=list[ConversationPreviewResponse])
async def list_conversations(creator: CurrentCreator, db: DbDep):
    previews = await _service(db).list_conversation_previews(creator.id if creator else None)
    return [
        ConversationPreviewResponse(
            id=user.id,
            name=user.name,
            image_id=user.image_id,
            chats=[ConversationPreviewItem(id=latest.id, body=latest.body)] if latest else [],
        )
        for user, latest in previews
    ]


@router.get("/context", response_model=AdditionalPromptResponse)
async def get_chat_context(user_id: int, creator: RequireCreator, db: DbDep):
    return AdditionalPromptResponse(additional_prompt=await _service(db).get_context(user_id))


@router.put("/context", response_model=AdditionalPromptResponse)
async def set_chat_context(
    user_id: int, data: AdditionalPromptUpdate, creator: RequireCreator, db: DbDep
):
    additional_prompt = await _service(db).set_context(user_id, data.additional_prompt)
    return AdditionalPromptResponse(additional_prompt=additional_prompt)


@router.get("/messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(user_id: int, db: DbDep):
    return await _service(db).list_messages(user_id)


@router.post("/messages", response_model=ChatMessageResponse)
async def add_chat_message(user_id: int, data: ChatMessageCreate, db: DbDep):
    return await _service(db).add_user_message(user_id, data.message)


@router.delete("/messages/{message_id}", status_code=204)
async def delete_chat_message(user_id: int, message_id: int, db: DbDep):
    await _service(db).delete_message(message_id)


@router.post("/messages/{message_id}/translate", response_model=TranslateResponse)
async def translate_chat_message(
    user_id: int, message_id: int, db: DbDep, chat_model: ChatModelPref
):
    body_en = await _service(db).translate_message(user_id, message_id, chat_model)
    return TranslateResponse(body_en=body_en)


@router.post("/respond", response_model=ChatMessageResponse)
async def respond_to_chat(
    user_id: int, creator: CurrentCreator, db: DbDep, chat_model: ChatModelPref
):
    return await _service(db).generate_response(user_id, creator, chat_model)


@router.post("/new-conversation", response_model=ChatMessageResponse)
async def start_new_conversation(
    user_id: int, creator: CurrentCreator, db: DbDep, chat_model: ChatModelPref
):
    return await _service(db).start_new_conversation(user_id, creator, chat_model)
