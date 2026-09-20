"""Pydantic models for Character Card V1/V2/V3 and character books.

Round-trip fidelity is a hard requirement: the spec says editors *must not*
destroy unknown key-value pairs. Every model therefore allows extra fields and
`extensions` is an open mapping, so importing then exporting a card preserves
keys this application does not understand.

Presence of fields is treated leniently (real-world cards omit things the spec
calls mandatory) while *types* are validated strictly.

Canonical storage keeps the format a card arrived in: V1/V2 cards stay V2-shaped
and V3 cards stay V3-shaped. V3 is a superset of V2, so `dump_v2`/`dump_v3`
convert on demand for export.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CardFields(BaseModel):
    """The six fields shared by V1, V2, and V3 (nested under `data` after V1)."""

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

    # V3 additions. Optional so a V2 card does not gain a `use_regex: false`
    # default on a round trip; `None` behaves as false when matching.
    use_regex: bool | None = None

    # Present in the spec but not used for prompt engineering.
    name: str | None = None
    priority: int | float | None = None
    id: int | str | None = None
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


class LorebookEnvelope(BaseModel):
    """A lorebook exported on its own, per the V3 spec's `lorebook_v3` shape."""

    model_config = ConfigDict(extra="allow")

    spec: str = "lorebook_v3"
    data: CharacterBook = Field(default_factory=CharacterBook)


class CardAsset(BaseModel):
    """One entry of a V3 card's `assets` array."""

    model_config = ConfigDict(extra="allow")

    type: str = ""
    uri: str = ""
    name: str = ""
    ext: str = ""

    @field_validator("ext", mode="before")
    @classmethod
    def _normalize_ext(cls, value: Any) -> Any:
        """The spec requires a lowercase extension without the leading dot."""
        if isinstance(value, str):
            return value.strip().lstrip(".").lower()
        return value


# The assets a card is documented to behave as if it declared when `assets` is
# absent (a PNG/CHARX icon is the character's own image).
DEFAULT_ASSETS: tuple[CardAsset, ...] = (
    CardAsset(type="icon", uri="ccdefault:", name="main", ext="png"),
)


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


class CharacterCardDataV3(CharacterCardData):
    """The `data` object of a V3 card: V2 plus the V3-only fields."""

    nickname: str | None = None
    creator_notes_multilingual: dict[str, str] | None = None
    source: list[str] | None = None
    assets: list[CardAsset] | None = None
    # MUST be present, may be empty.
    group_only_greetings: list[str] = Field(default_factory=list)
    creation_date: int | float | None = None
    modification_date: int | float | None = None


class TavernCardV1(CardFields):
    """A V1 card: the six shared fields at the top level."""


class TavernCardV2(BaseModel):
    """A V2 card: `spec`, `spec_version`, and everything else under `data`."""

    model_config = ConfigDict(extra="allow")

    spec: str = "chara_card_v2"
    spec_version: str = "2.0"
    data: CharacterCardData


class TavernCardV3(BaseModel):
    """A V3 card. A superset of V2; `data` adds the V3 fields."""

    model_config = ConfigDict(extra="allow")

    spec: str = "chara_card_v3"
    spec_version: str = "3.0"
    data: CharacterCardDataV3


# A stored card, in whichever format it arrived in.
CharacterCard = TavernCardV2 | TavernCardV3
