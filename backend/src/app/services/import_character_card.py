"""SillyTavern-style character card (chara_card_v2) parser.

Ported 1:1 from `src/lib/server/import-character-card.ts` — pure logic, no I/O, so this is a
near-mechanical translation. Keep this in sync with that file's regex patterns and heuristics
until the TS side is removed (see BACKEND_MIGRATION.md).
"""

import re

from pydantic import BaseModel, Field


class CharacterCardData(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    alternate_greetings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class CharacterCardV2(BaseModel):
    spec: str
    spec_version: str = ""
    data: CharacterCardData

    model_config = {"extra": "allow"}


class ParsedCharacterCard(BaseModel):
    name: str
    age: int
    pronouns: str
    bio: str
    personality_traits: str
    backstory: str
    appearance: str
    writing_style: str
    interests: list[str]
    occupation: str
    location: dict[str, str]
    relationship_status: str
    scenario: str
    first_mes: str
    additional_prompt: str


_SECTION_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    ("name", [re.compile(r"\[Name:\s*(.+?)\]", re.I), re.compile(r"Name:\s*(.+)", re.I)]),
    ("age", [re.compile(r"\[Age:\s*(\d+)\]", re.I), re.compile(r"Age:\s*(\d+)", re.I)]),
    ("gender", [re.compile(r"\[Gender:\s*(.+?)\]", re.I), re.compile(r"Gender:\s*(.+)", re.I)]),
    (
        "appearance",
        [
            re.compile(r"\[Appearance:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Appearance:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    (
        "personality",
        [
            re.compile(r"\[Personality:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Personality:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    (
        "speech",
        [
            re.compile(r"\[Speech:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Speech:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    (
        "likes",
        [
            re.compile(r"\[Likes:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Likes:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    (
        "description",
        [
            re.compile(r"\[Description:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Description:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    (
        "backstory",
        [
            re.compile(r"\[Backstory:\s*([\s\S]*?)(?=\[|\n\n|$)", re.I),
            re.compile(r"Backstory:\s*([\s\S]*?)(?=\n\n|$)", re.I),
        ],
    ),
    ("role", [re.compile(r"\[Role:\s*(.+?)\]", re.I), re.compile(r"Role:\s*(.+)", re.I)]),
]


def _extract_sections(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, patterns in _SECTION_PATTERNS:
        for pattern in patterns:
            match = pattern.search(text)
            if match and match.group(1):
                result[key] = match.group(1).strip()
                break
    return result


def _extract_likes_as_tags(text: str) -> list[str]:
    sections = _extract_sections(text)
    likes = sections.get("likes")
    if not likes:
        return []
    return [
        re.sub(r"^and\s+", "", part.strip(), flags=re.I)
        for part in likes.split(",")
        if part.strip()
    ]


def _infer_pronouns_from_description(gender: str | None) -> str:
    if not gender:
        return "they/them"
    g = gender.lower()
    if any(word in g for word in ("female", "woman", "girl")):
        return "she/her"
    if any(word in g for word in ("male", "man", "boy")):
        return "he/him"
    return "they/them"


def _infer_relationship_status(description: str) -> str:
    if re.search(r"wife|husband|married|spouse", description, re.I):
        return "Married"
    if re.search(r"single", description, re.I):
        return "Single"
    if re.search(r"divorced", description, re.I):
        return "Divorced"
    if re.search(r"dating", description, re.I):
        return "Dating"
    return "Single"


def parse_character_card(card: CharacterCardV2, creator_id: int | None = None) -> ParsedCharacterCard:
    data = card.data
    sections = _extract_sections(data.description)

    bio = re.sub(r"\[.*?\]", "", data.description).strip() if data.description else ""
    bio = bio or f"{data.name} character."

    personality = data.personality or sections.get("personality", "")
    appearance = sections.get("appearance", "")
    speech_pattern = sections.get("speech", "")
    likes = data.tags if data.tags else _extract_likes_as_tags(data.description)
    description_section = sections.get("description", "")
    backstory_text = sections.get("backstory") or description_section or data.description[:500]

    additional_prompt_parts = [
        part
        for part in [
            f"Creator notes:\n{data.creator_notes}" if data.creator_notes else None,
            f"System prompt:\n{data.system_prompt}" if data.system_prompt else None,
            (
                f"Post history instructions:\n{data.post_history_instructions}"
                if data.post_history_instructions
                else None
            ),
            f"Example messages:\n{data.mes_example}" if data.mes_example else None,
            (
                "Alternate greetings:\n" + "\n---\n".join(data.alternate_greetings)
                if data.alternate_greetings
                else None
            ),
        ]
        if part
    ]

    return ParsedCharacterCard(
        name=data.name,
        age=int(sections["age"]) if sections.get("age") else 25,
        pronouns=_infer_pronouns_from_description(sections.get("gender")),
        bio=bio,
        personality_traits=personality,
        backstory=backstory_text,
        appearance=appearance,
        writing_style=speech_pattern,
        interests=likes,
        occupation=sections.get("role") or "Unknown",
        location={"city": "Unknown", "state_province": "Unknown", "country": "Unknown"},
        relationship_status=_infer_relationship_status(data.description),
        scenario=data.scenario or "",
        first_mes=data.first_mes or "",
        additional_prompt="\n\n".join(additional_prompt_parts),
    )
