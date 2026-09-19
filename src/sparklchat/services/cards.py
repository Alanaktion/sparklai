"""Parsing, validation, and format conversion for Character Cards."""

from typing import Any, Literal

from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.card import CharacterCardData, TavernCardV1, TavernCardV2
from sparklchat.models.character import (
    Character,
    CharacterDetail,
    CharacterSummary,
    CharacterTag,
)

CardFormat = Literal["v1", "v2"]

# Keys the card envelope owns; a V1 card must not smuggle them through.
_RESERVED_KEYS = frozenset({"spec", "spec_version", "data"})


class CardError(ValueError):
    """Raised when a card cannot be parsed or uses an unsupported spec."""


def detect_format(raw: dict[str, Any]) -> CardFormat:
    """Classify a card as V1 or V2, raising `CardError` for anything else."""
    spec = raw.get("spec")
    if spec == "chara_card_v2":
        return "v2"
    if spec is not None:
        raise CardError(
            f"unsupported character card spec {spec!r}; only Character Card V1 and V2 are supported"
        )
    # V1 cards have no `spec`; some V2 cards omit it but keep a `data` object.
    return "v2" if isinstance(raw.get("data"), dict) else "v1"


def parse_card(raw: dict[str, Any]) -> tuple[TavernCardV2, CardFormat]:
    """Validate a V1 or V2 card and return the canonical V2 form plus its origin."""
    if not isinstance(raw, dict):
        raise CardError("character card must be a JSON object")
    source = detect_format(raw)
    card = upconvert_v1(raw) if source == "v1" else parse_v2(raw)
    return card, source


def parse_v2(raw: dict[str, Any]) -> TavernCardV2:
    spec_version = raw.get("spec_version")
    if spec_version is not None and not _is_version_2(spec_version):
        raise CardError(
            f"unsupported character card spec_version {spec_version!r}; only '2.0' is supported"
        )
    try:
        card = TavernCardV2.model_validate(raw)
    except ValidationError as exc:
        raise CardError(_describe(exc)) from exc
    # Early V2 cards predate `spec_version`, so normalise rather than reject.
    card.spec = "chara_card_v2"
    card.spec_version = "2.0"
    return card


def upconvert_v1(raw: dict[str, Any]) -> TavernCardV2:
    """Wrap a V1 card into V2 shape, filling the V2 defaults.

    Unknown top-level V1 keys are kept on the V2 card so exporting back to V1
    returns them unchanged.
    """
    try:
        v1 = TavernCardV1.model_validate(raw)
    except ValidationError as exc:
        raise CardError(_describe(exc)) from exc

    data = CharacterCardData(
        name=v1.name,
        description=v1.description,
        personality=v1.personality,
        scenario=v1.scenario,
        first_mes=v1.first_mes,
        mes_example=v1.mes_example,
    )
    extra = {
        key: value for key, value in (v1.model_extra or {}).items() if key not in _RESERVED_KEYS
    }
    return TavernCardV2(spec="chara_card_v2", spec_version="2.0", data=data, **extra)


def dump_v2(card: TavernCardV2) -> dict[str, Any]:
    """Serialise the canonical V2 JSON, dropping unset optional fields."""
    return card.model_dump(mode="json", exclude_none=True)


def dump_v1(card: TavernCardV2) -> dict[str, Any]:
    """Export the six V1 fields un-nested, keeping any carried-over extras."""
    data = card.data
    legacy: dict[str, Any] = {
        "name": data.name,
        "description": data.description,
        "personality": data.personality,
        "scenario": data.scenario,
        "first_mes": data.first_mes,
        "mes_example": data.mes_example,
    }
    for key, value in (card.model_extra or {}).items():
        legacy.setdefault(key, value)
    return legacy


def character_summary(character: Character) -> CharacterSummary:
    """Build the listing view, reading denormalized fields out of the card."""
    data = character.card_json.get("data") or {}
    return CharacterSummary(
        id=character.id or 0,
        name=character.name,
        spec_version=character.spec_version,
        source=character.source,
        tags=[str(tag) for tag in data.get("tags") or []],
        creator=character.creator,
        character_version=character.character_version,
        has_avatar=bool(character.avatar_path),
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


def normalize_tag(tag: str) -> str:
    """Tags are matched case-insensitively, so they are stored folded."""
    return tag.strip().lower()[:100]


async def apply_card_metadata(db: AsyncSession, character: Character, card: TavernCardV2) -> None:
    """Refresh the denormalized columns and tag rows from a card.

    Flushes after setting the columns: that populates the NOT NULL `name` before
    the row is inserted, and gives a brand-new character an id for its tag rows.
    """
    character.name = card.data.name
    character.spec_version = card.spec_version
    character.creator = card.data.creator
    character.character_version = card.data.character_version

    db.add(character)
    await db.flush()

    existing = (
        await db.exec(select(CharacterTag).where(CharacterTag.character_id == character.id))
    ).all()
    for row in existing:
        await db.delete(row)

    for tag in dict.fromkeys(normalize_tag(tag) for tag in card.data.tags):
        if tag:
            db.add(CharacterTag(character_id=character.id, tag=tag))


def character_detail(character: Character) -> CharacterDetail:
    return CharacterDetail(**character_summary(character).model_dump(), card=character.card_json)


def _is_version_2(value: Any) -> bool:
    try:
        return float(value) == 2.0
    except (TypeError, ValueError):
        return False


def _describe(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors()[:5]:
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        problems.append(f"{location}: {error['msg']}")
    return "invalid character card: " + "; ".join(problems)
