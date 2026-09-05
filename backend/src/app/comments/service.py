from app.comments.repository import CommentRepository
from app.db.models import Comment, Post, User
from app.exceptions import BadRequestError, NotFoundError
from app.services import chat
from app.services.chat import LlamaMessage


class CommentService:
    def __init__(self, repository: CommentRepository):
        self._repository = repository

    async def get_post_or_raise(self, post_id: int) -> Post:
        post = await self._repository.get_post(post_id)
        if not post:
            raise NotFoundError("Post", post_id)
        return post

    async def get_user_or_raise(self, user_id: int) -> User:
        user = await self._repository.get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def get_random_active_user_or_raise(self) -> User:
        user = await self._repository.get_random_active_user()
        if not user:
            raise NotFoundError("No Users Found")
        return user

    async def get_random_recent_post_or_raise(self) -> Post:
        post = await self._repository.get_random_recent_post()
        if not post:
            raise NotFoundError("No Posts Found")
        return post

    async def create_comment(self, post_id: int, message: str) -> Comment:
        """A plain (non-AI) user comment."""
        if not message.strip():
            raise BadRequestError("message is required")
        comment = await self._repository.create(post_id=post_id, user_id=None, body=message)
        return await self._repository.get_with_user(comment.id)

    async def delete_comment(self, comment_id: int) -> None:
        await self._repository.delete(comment_id)

    async def translate_comment(
        self, post_id: int, comment_id: int, model: str | None = None
    ) -> str:
        comment = await self._repository.get_by_id_and_post(comment_id, post_id)
        if not comment:
            raise NotFoundError("Comment", comment_id)
        if comment.body_en:
            return comment.body_en
        body_en = await chat.translate_to_english(comment.body, model=model)
        await self._repository.update_body_en(comment, body_en)
        return body_en

    async def generate_comment_for_post(
        self, post: Post, commenter: User, model: str | None = None
    ) -> Comment:
        author = await self.get_user_or_raise(post.user_id)
        is_own_post = commenter.id == author.id

        relationship_context = ""
        if not is_own_post:
            relationship = await self._repository.get_relationship(commenter.id, author.id)
            if relationship:
                relationship_context = f"\nYour relationship with {author.name}"
                if relationship.relationship_type:
                    relationship_context += f": {relationship.relationship_type}"
                if relationship.description:
                    relationship_context += f" - {relationship.description}"

        system_prompt = (
            f"You are {commenter.name} ({commenter.pronouns}), writing a comment on the given "
            "social media post. It can be a reply to other comments (if any), or directly "
            "responding to the post itself. *Do not include any meta-text, only the comment "
            "body.*\n"
            f"Your backstory: {commenter.backstory}\n"
            f"Writing style: {commenter.writing_style}\n"
            f"{relationship_context}"
            "Write a new comment. Do not include any roleplay or metatext, just write the actual "
            "response. If you don't know the language the original post is in, you can use your "
            "preferred language. Most comments are short, but if you feel the need to write a "
            "longer comment to be authentic to the character and the post, you can do that as "
            "well."
        )

        history: list[LlamaMessage] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"This is your own post that you wrote: {post.body}"
                    if is_own_post
                    else f"Post by {author.name} ({author.pronouns}): {post.body}"
                ),
            },
        ]

        prior_comments = await self._repository.list_for_post_with_commenter_name(post.id)
        for body, commenter_name in prior_comments:
            history.append({"role": "user", "content": f"Comment by {commenter_name}: {body}"})

        response = await chat.completion(None, history, model=model)

        comment = await self._repository.create(post_id=post.id, user_id=commenter.id, body=response)
        return await self._repository.get_with_user(comment.id)
