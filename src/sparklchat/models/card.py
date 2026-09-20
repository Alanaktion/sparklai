"""Pydantic models for Character Card V1/V2 and character books.

Round-trip fidelity is a hard requirement: the spec says editors *must not*
destroy unknown key-value pairs. Every model therefore allows extra fields and
`extensions` is an open mapping, so importing then exporting a card preserves
keys this application does not understand.

Presence of fields is treated leniently (real-world cards omit things the spec
calls mandatory) while *types* are validated strictly.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CardFields(BaseModel):
    """The six fields shared by V1 and V2 (nested under `data` in V2)."""

    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""


class CharacterBookEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    keys: list[str] = Field(default_factory=list)
    content: str = ""
    extensions: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    insertion_order: int | float = 0
    case_sensitive: bool = False

    # Present in the spec but not used for prompt engineering.
    name: str | None = None
    priority: int | float | None = None
    id: int | None = None
    comment: str | None = None

    # Trigger behaviour.
    selective: bool = False
    secondary_keys: list[str] | None = None
    constant: bool = False
    position: Literal["before_char", "after_char"] | None = None

    @field_validator("position", mode="before")
    @classmethod
    def _blank_position_is_absent(cls, value: Any) -> Any:
        """Treat a blank `position` as the documented `before_char` default.

        Real-world exports (e.g. Chub, SillyTavern) often write `"position": ""`
        for entries that use the default placement. A blank string carries no
        information, so it normalises to absent rather than failing validation;
        unknown non-blank values are still rejected by the `Literal`.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CharacterBook(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    description: str | None = None
    scan_depth: int | float | None = None
    token_budget: int | float | None = None
    recursive_scanning: bool | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)
    entries: list[CharacterBookEntry] = Field(default_factory=list)


class CharacterCardData(CardFields):
    """The `data` object of a V2 card."""

    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    alternate_greetings: list[str] = Field(default_factory=list)
    character_book: CharacterBook | None = None

    tags: list[str] = Field(default_factory=list)
    creator: str = ""
    character_version: str = ""
    extensions: dict[str, Any] = Field(default_factory=dict)


class TavernCardV1(CardFields):
    """A V1 card: the six shared fields at the top level."""


class TavernCardV2(BaseModel):
    """A V2 card: `spec`, `spec_version`, and everything else under `data`."""

    model_config = ConfigDict(extra="allow")

    spec: str = "chara_card_v2"
    spec_version: str = "2.0"
    data: CharacterCardData
