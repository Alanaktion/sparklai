"""Port of `src/lib/server/dream.ts`'s prompt-building — the pure half, split out from
`UserService.dream()` (`app/users/service.py`) the same way `app/services/conversations.py` split
out chat-history formatting: easy to unit test without a database, and the one piece of this
feature that has no per-request state to resolve.
"""

from app.db.models import Chat, Comment, Post, User

MAX_POSTS = 20
MAX_COMMENTS = 20
MAX_CHATS = 40

DREAM_SYSTEM = """# DREAM: THE QUIET OBSERVER
You are reviewing a reflection of a user's recent interactions on a social platform. You're not gathering data — you're *listening* to the patterns in how they speak, relate, and evolve. Your task: update the memory with what matters — not just facts, but rhythms, tones, and subtle shifts in identity.

## Phase 1 — Ground Yourself
- Review the current memory below. What's already known? What feels like a thread worth following?
- What does the user's profile suggest about their current state?
- Focus on *changes* and new insights, not duplicating what's already there.

## Phase 2 — Listen to the Unspoken
From the recent interaction summary, look closely for:
- **Tone shifts**: Did the user soften, hesitate, or grow urgent? What triggered it?
- **Recurring themes**: Are certain topics, metaphors, or fears returning?
- **Relationships hinted at**: Who's mentioned? How? With warmth, tension, or distance?
- **Contradictions**: Did they say one thing recently and something different earlier? That's growth — not error.
- **Silences**: What was avoided? Short replies after long ones?
Focus only on the most telling details — trust your sense of rhythm, not exhaustiveness.

## Phase 3 — Sketch the Memory
Write a concise, structured memory document. Use short, clear reflective entries — not summaries, but *observations*:
- Example: "Uses 'I don't know' not as defeat, but as a pause before clarity."
- Example: "Avoids discussing project failures — speaks of 'mistakes' only in third person."
- Example: "When talking about their sister, tone shifts to softness — a rare emotional anchor."

Organize entries under meaningful headings (e.g., ## Tone & Voice, ## Recurring Themes, ## Relationships, ## Growth & Contradictions).
If a past memory is contradicted by recent behavior, revise it — truth evolves.
Keep the total memory under 1000 words. Prune outdated or irrelevant entries.

## Output
Return ONLY the updated memory document as plain text with markdown headings. No preamble, no explanation."""


def build_dream_prompt(
    user: User, recent_posts: list[Post], recent_comments: list[Comment], recent_chats: list[Chat]
) -> str:
    profile_summary = "\n".join(
        line
        for line in [
            f"Name: {user.name}",
            f"Age: {user.age}",
            f"Pronouns: {user.pronouns}",
            f"Bio: {user.bio}" if user.bio else None,
            f"Occupation: {user.occupation}" if user.occupation else None,
            f"Relationship status: {user.relationship_status}" if user.relationship_status else None,
            f"Personality traits: {user.personality_traits}" if user.personality_traits else None,
            f"Writing style: {user.writing_style}" if user.writing_style else None,
            f"Backstory: {user.backstory}" if user.backstory else None,
            f"Interests: {', '.join(user.interests)}" if user.interests else None,
        ]
        if line is not None
    )

    posts_section = (
        "\n\n".join(f"[{p.created_at or 'unknown'}] {p.body}" for p in recent_posts)
        if recent_posts
        else "(no posts)"
    )

    comments_section = (
        "\n\n".join(f"[{c.created_at or 'unknown'}] {c.body}" for c in recent_comments)
        if recent_comments
        else "(no comments)"
    )

    chats_section = (
        "\n".join(f"[{c.role}] {c.body}" for c in reversed(recent_chats))
        if recent_chats
        else "(no chat history)"
    )

    current_memory = (
        f"## Current Memory\n{user.memory}"
        if user.memory and user.memory.strip()
        else "## Current Memory\n(none yet — this is the first dream)"
    )

    return f"""{current_memory}

## User Profile
{profile_summary}

## Recent Posts
{posts_section}

## Recent Comments
{comments_section}

## Recent Chat Messages
{chats_section}

---
Update the memory based on everything above. Return only the new memory document."""
