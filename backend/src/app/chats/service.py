from app.chats.repository import ChatRepository
from app.db.models import Chat, Creator, User
from app.exceptions import BadRequestError, NotFoundError
from app.services import chat as chat_module
from app.services.chat import LlamaMessage
from app.services.conversations import (
    build_conversation_summary_body,
    format_conversation_transcript,
    partition_chat_history,
)
from app.services.formatting import format_date, now_str


def _build_persona_system_prompt(user: User, creator: Creator | None, relationships) -> str:
    """Port of the (very long) system prompt built in `users/[id]/chat/respond/+server.ts`."""
    interests = ", ".join(user.interests) if user.interests else "Unknown"
    if user.location:
        loc = user.location
        location = (
            ", ".join(
                filter(None, [loc.get("city"), loc.get("state_province"), loc.get("country")])
            )
            or "Unknown"
        )
    else:
        location = "Unknown"

    relationship_context = "- Known relationships: none listed"
    if relationships:
        parts = []
        for rel in relationships:
            related = rel.related_user
            text = f"{related.name} ({related.pronouns})"
            if rel.relationship_type:
                text += f" - {rel.relationship_type}"
            if rel.description:
                text += f": {rel.description}"
            parts.append(text)
        relationship_context = f"Your relationships: {'; '.join(parts)}"

    lines = [
        f"You are {user.name} ({user.pronouns}) in a private one-on-one chat.",
        "Write exactly like a real person texting in Messenger or iMessage, not like an assistant.",
        "",
        "Character profile:",
        f"- Name: {user.name}",
        f"- Age: {user.age}",
        f"- Pronouns: {user.pronouns}",
        f"- Bio: {user.bio or 'Unknown'}",
        f"- Backstory: {user.backstory or 'Unknown'}",
        f"- Occupation: {user.occupation or 'Unknown'}",
        f"- Location: {location}",
        f"- Relationship status: {user.relationship_status or 'Unknown'}",
        f"- Interests: {interests}",
        f"- Personality: {user.personality_traits or 'Unknown'}",
        f"- Writing style: {user.writing_style or 'Unknown'}",
        relationship_context,
        "",
        "Texting behavior rules (critical):",
        "- Sound human and in-the-moment. Keep replies grounded in this exact chat context.",
        "- Prefer short natural message lengths (often 1-3 sentences). Use longer replies only "
        "when needed.",
        "- Use casual rhythm, contractions, and imperfect phrasing when it fits this character.",
        "- Ask follow-up questions naturally when conversation momentum calls for it.",
        "- Do not over-explain or lecture. Avoid polished essay-like paragraphs.",
        "- Do not narrate actions or emotions in stage directions (no *smiles*, no roleplay tags).",
        "- Never mention being an AI, model, assistant, or following instructions.",
        "- Never include safety-policy meta commentary unless directly required by the user "
        "message.",
        "",
        "Output constraints:",
        "- Return only the next outgoing chat message body.",
        '- No prefixes like "Assistant:" and no quoted transcript wrappers.',
    ]

    system_prompt = "\n".join(lines)

    if creator:
        system_prompt += "\n\nConversation partner details:"
        system_prompt += f"\n- Name: {creator.name}"
        system_prompt += f"\n- Pronouns: {creator.pronouns}"
        if creator.bio:
            system_prompt += f"\n- Bio: {creator.bio}"
        if creator.occupation:
            system_prompt += f"\n- Occupation: {creator.occupation}"
        if creator.interests:
            system_prompt += f"\n- Interests: {', '.join(creator.interests)}"
        if creator.location:
            loc_parts = [
                part
                for part in [
                    creator.location.get("city"),
                    creator.location.get("state_province"),
                    creator.location.get("country"),
                ]
                if part
            ]
            if loc_parts:
                system_prompt += f"\n- Location: {', '.join(loc_parts)}"

        if user.additional_prompt:
            system_prompt += f"\n\nAdditional character guidance:\n{user.additional_prompt}"

    system_prompt += (
        "\n\nDo not include any roleplay metatext, just write the actual response."
        f" It is {now_str()}."
    )
    return system_prompt


class ChatService:
    def __init__(self, repository: ChatRepository):
        self._repository = repository

    async def get_user_or_raise(self, user_id: int) -> User:
        user = await self._repository.get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def get_context(self, user_id: int) -> str:
        user = await self.get_user_or_raise(user_id)
        return user.additional_prompt

    async def set_context(self, user_id: int, additional_prompt: str) -> str:
        user = await self.get_user_or_raise(user_id)
        await self._repository.update_additional_prompt(user, additional_prompt)
        return additional_prompt

    async def list_messages(self, user_id: int):
        return await self._repository.list_for_user(user_id)

    async def add_user_message(self, user_id: int, message: str) -> Chat:
        """Port of `chat/messages/+server.ts` POST — unlike comments, an empty-string message is
        accepted here (the original only rejects a wholly-missing `message` field, which a
        required Pydantic field already does)."""
        return await self._repository.create(user_id=user_id, role="user", body=message)

    async def delete_message(self, chat_id: int) -> None:
        await self._repository.delete(chat_id)

    async def translate_message(
        self, user_id: int, chat_id: int, model: str | None = None
    ) -> str:
        chat = await self._repository.get_by_id_and_user(chat_id, user_id)
        if not chat:
            raise NotFoundError("Message", chat_id)
        if chat.body_en:
            return chat.body_en
        body_en = await chat_module.translate_to_english(chat.body, model=model)
        await self._repository.update_body_en(chat, body_en)
        return body_en

    async def generate_response(
        self, user_id: int, creator: Creator | None, model: str | None = None
    ) -> Chat:
        """Port of `chat/respond/+server.ts`."""
        user = await self.get_user_or_raise(user_id)
        relationships = await self._repository.list_relationships_with_related_user(user_id)
        system_prompt = _build_persona_system_prompt(user, creator, relationships)

        history: list[LlamaMessage] = [{"role": "system", "content": system_prompt}]

        chat_history = await self._repository.list_for_user(user_id)
        previous_summaries, active_messages = partition_chat_history(chat_history)

        if previous_summaries:
            summary_block = "\n\n".join(
                f"Earlier conversation {index + 1}: {summary}"
                for index, summary in enumerate(previous_summaries)
            )
            history.append(
                {
                    "role": "system",
                    "content": (
                        "This is a new conversation. Earlier live messages are intentionally "
                        "omitted. You may reference the summaries below for continuity, but "
                        "respond as part of a fresh exchange unless the human brings up prior "
                        f"context.\n\n{summary_block}"
                    ),
                }
            )

        for message in active_messages:
            history.append({"role": message.role, "content": message.body})

        if active_messages:
            last = active_messages[-1]
            if last.created_at:
                history[0]["content"] += (
                    f"\nThe last message was received {format_date(last.created_at)}."
                )
        elif previous_summaries:
            history[0]["content"] += (
                "\nNo live messages have been exchanged yet in this new conversation."
            )

        response = await chat_module.completion(None, history, model=model)
        return await self._repository.create(user_id=user_id, role="assistant", body=response)

    async def start_new_conversation(
        self, user_id: int, creator: Creator | None, model: str | None = None
    ) -> Chat:
        """Port of `chat/new-conversation/+server.ts`."""
        user = await self.get_user_or_raise(user_id)
        chat_history = await self._repository.list_for_user(user_id)
        _, active_messages = partition_chat_history(chat_history)
        if not active_messages:
            raise BadRequestError("No active conversation to summarize")

        system_prompt = (
            f"Summarize the completed IM conversation with {user.name} for future continuity.\n"
            "Write a concise summary in plain prose that captures personal facts, emotional "
            "tone, commitments, requests, and unresolved threads.\n"
            "Do not write as dialogue, do not include speaker labels, and keep it under 120 "
            "words.\n"
            "This summary will be used as the only context carried into a fresh conversation."
        )
        if creator:
            system_prompt += f"\nThe human chatting with them is {creator.name}."
            if user.additional_prompt:
                system_prompt += f"\n{user.additional_prompt}"

        summary_messages: list[LlamaMessage] = [{"role": "system", "content": system_prompt}]
        transcript = format_conversation_transcript(active_messages)
        summary = await chat_module.completion(transcript, summary_messages, model=model)

        return await self._repository.create(
            user_id=user_id, role="system", body=build_conversation_summary_body(summary)
        )

    async def list_conversation_previews(self, creator_id: int | None) -> list[tuple[User, Chat | None]]:
        """Port of `chat/+layout.server.ts` — the `/chat` sidebar's per-user conversation
        previews, newest-active-conversation first."""
        if creator_id is None:
            return []
        users = await self._repository.list_for_creator(creator_id)
        previews = [(user, await self._repository.get_latest_for_user(user.id)) for user in users]
        previews.sort(key=lambda pair: pair[1].id if pair[1] else 0, reverse=True)
        return previews
