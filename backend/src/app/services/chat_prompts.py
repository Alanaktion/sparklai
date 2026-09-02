"""System prompts, ported from `src/lib/server/chat/schema/index.ts`.

`post_image_system`/`profile_image_system` aren't ported yet — they belong to the image-generation
pipeline (BACKEND_MIGRATION.md item 4), not this pass.
"""

POST_SYSTEM = """Generate a realistic social media post as JSON.

Write like a specific person, not like an assistant. Match the user's age, personality, interests, bio, relationships, life situation, and writing style closely.

The post_text field must:
- contain only the body of the post
- avoid formulaic openings and generic scene-setting
- sound natural, varied, and specific to the character
- reflect the character's likely language, tone, slang, punctuation, and emoji usage
- avoid hashtags unless the user prompt explicitly requires them

Only include image_generation when an image would feel natural for this specific post."""

USER_SYSTEM = (
    "Generate a realistic user profile as a JSON object, adhering to the provided schema for "
    "data types and constraints."
)
