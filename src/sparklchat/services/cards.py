"""Parsing, validation, and format conversion for Character Cards.

V1, V2, and V3 cards all normalise into a validated card model: V1 is wrapped
into V2 shape (keeping unknown top-level keys so a V1 export round-trips), while
V2 and V3 keep their own envelope. V3 is a superset of V2, so conversion between
them is lossless one way and drops only the V3-only fields the other way.
"""

import time
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.card import (
    DEFAULT_ASSETS,
    CardAsset,
    CharacterBook,
    CharacterCard,
    CharacterCardData,
    CharacterCardDataV3,
    LorebookEnvelope,
    TavernCardV1,
    TavernCardV2,
    TavernCardV3,
)
from sparklchat.models.character import (
    Character,
    CharacterDetail,
    CharacterSummary,
    CharacterTag,
)
from sparklchat.models.hooks import hooks_from_card_json
from sparklchat.services.decorators import strip_decorators

CardFormat = Literal["v1", "v2", "v3"]

# Keys the card envelope owns; a V1 card must not smuggle them through.
_RESERVED_KEYS = frozenset({"spec", "spec_version", "data"})

# Fields V3 adds to `data`; a V2 export must not carry them.
_V3_ONLY_KEYS = frozenset(
    {
        "nickname",
        "creator_notes_multilingual",
        "source",
        "assets",
        "group_only_greetings",
        "creation_date",
        "modification_date",
    }
)


class CardError(ValueError):
    """Raised when a card cannot be parsed or uses an unsupported spec."""


def detect_format(raw: dict[str, Any]) -> CardFormat:
    """Classify a card as V1, V2, or V3, raising `CardError` for anything else."""
    spec = raw.get("spec")
    if spec == "chara_card_v3":
        return "v3"
    if spec == "chara_card_v2":
        return "v2"
    if spec is not None:
        raise CardError(
            f"unsupported character card spec {spec!r}; "
            "only Character Card V1, V2, and V3 are supported"
        )
    # V1 cards have no `spec`; some V2 cards omit it but keep a `data` object.
    return "v2" if isinstance(raw.get("data"), dict) else "v1"


def parse_card(raw: dict[str, Any]) -> tuple[CharacterCard, CardFormat]:
    """Validate a V1/V2/V3 card and return it plus the format it arrived in."""
    if not isinstance(raw, dict):
        raise CardError("character card must be a JSON object")
    source = detect_format(raw)
    if source == "v3":
        return parse_v3(raw), source
    if source == "v2":
        return parse_v2(raw), source
    return upconvert_v1(raw), source


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


def parse_v3(raw: dict[str, Any]) -> TavernCardV3:
    """Validate a V3 card.

    `spec_version` is deliberately not constrained: the spec asks applications to
    accept older and newer point releases of V3 and only warn about the newer
    ones (`spec_warnings`).
    """
    try:
        card = TavernCardV3.model_validate(raw)
    except ValidationError as exc:
        raise CardError(_describe(exc)) from exc
    card.spec = "chara_card_v3"
    version = raw.get("spec_version")
    card.spec_version = str(version) if version not in (None, "") else "3.0"
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


def load_card(card_json: dict[str, Any]) -> CharacterCard:
    """Validate stored canonical JSON into the matching card model.

    Unlike `parse_card` this does not re-run the version checks: the JSON has
    already been through `parse_card` when it was written.
    """
    if card_json.get("spec") == "chara_card_v3":
        return TavernCardV3.model_validate(card_json)
    return TavernCardV2.model_validate(card_json)


def to_v3(card: CharacterCard) -> TavernCardV3:
    """Return the card as a V3 card, filling the V3 defaults when needed."""
    if isinstance(card, TavernCardV3):
        return card

    data = CharacterCardDataV3.model_validate(card.data.model_dump(mode="json", exclude_none=True))
    extra = card.model_extra or {}
    return TavernCardV3(
        spec="chara_card_v3",
        spec_version="3.0",
        data=data,
        **extra,
    )


def to_v2(card: CharacterCard) -> TavernCardV2:
    """Return the card as a V2 card, dropping the V3-only data fields.

    V3 decorator lines are stripped from entry content, as the spec asks when a
    card is backfilled to V2 (a V2 reader would otherwise see them as text).
    """
    if isinstance(card, TavernCardV2):
        return card

    raw = card.data.model_dump(mode="json", exclude_none=True)
    stripped = {key: value for key, value in raw.items() if key not in _V3_ONLY_KEYS}
    _strip_entry_decorators(stripped.get("character_book"))
    data = CharacterCardData.model_validate(stripped)
    extra = card.model_extra or {}
    return TavernCardV2(spec="chara_card_v2", spec_version="2.0", data=data, **extra)


def _strip_entry_decorators(book: Any) -> None:
    if not isinstance(book, dict):
        return
    entries = book.get("entries")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("content"), str):
            entry["content"] = strip_decorators(entry["content"])


def dump_card(card: CharacterCard, card_format: CardFormat) -> dict[str, Any]:
    """Serialise a card in the requested export format."""
    if card_format == "v1":
        return dump_v1(card)
    if card_format == "v3":
        return dump_v3(card)
    return dump_v2(card)


def dump_v2(card: CharacterCard) -> dict[str, Any]:
    """Serialise the canonical V2 JSON, dropping unset optional fields."""
    target = card if isinstance(card, TavernCardV2) else to_v2(card)
    return target.model_dump(mode="json", exclude_none=True)


def dump_v3(card: CharacterCard) -> dict[str, Any]:
    """Serialise the canonical V3 JSON, dropping unset optional fields."""
    return to_v3(card).model_dump(mode="json", exclude_none=True)


def dump_v1(card: CharacterCard) -> dict[str, Any]:
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


def parse_lorebook(raw: dict[str, Any]) -> CharacterBook:
    """Accept either a bare V2 `CharacterBook` or a V3 `lorebook_v3` envelope."""
    if not isinstance(raw, dict):
        raise CardError("lorebook must be a JSON object")
    payload = raw.get("data") if raw.get("spec") == "lorebook_v3" else raw
    if not isinstance(payload, dict):
        raise CardError("lorebook must be a JSON object")
    try:
        return CharacterBook.model_validate(payload)
    except ValidationError as exc:
        raise CardError(_describe(exc)) from exc


def dump_lorebook(book: CharacterBook) -> dict[str, Any]:
    """Export a standalone lorebook using the V3 `lorebook_v3` envelope."""
    return LorebookEnvelope(data=book).model_dump(mode="json", exclude_none=True)


def stamp_creation(card_json: dict[str, Any]) -> dict[str, Any]:
    """Give a V3 card a `creation_date` if it does not already have one."""
    if card_json.get("spec") == "chara_card_v3":
        data = card_json.get("data")
        if isinstance(data, dict) and data.get("creation_date") is None:
            data["creation_date"] = int(time.time())
    return card_json


def stamp_modification(card_json: dict[str, Any]) -> dict[str, Any]:
    """Mark a V3 card as modified now, as the spec asks on export."""
    if card_json.get("spec") == "chara_card_v3":
        data = card_json.get("data")
        if isinstance(data, dict):
            data["modification_date"] = int(time.time())
    return card_json


def spec_warnings(card: CharacterCard) -> list[str]:
    """Alerts for cards the spec asks us to import but cannot fully honour."""
    version = _numeric_version(card.spec_version)
    if version is None or version <= 3.0:
        return []
    return [
        f"This character card was created with a newer version of the Character Card "
        f"spec ({card.spec_version}); newer features may not be supported."
    ]


def card_nickname(card: CharacterCard) -> str:
    """The name macros use: `nickname` when set, else `name`."""
    nickname = getattr(card.data, "nickname", None)
    if isinstance(nickname, str) and nickname.strip():
        return nickname.strip()
    return (card.data.name or "").strip() or "Character"


def card_assets(card: CharacterCard) -> list[CardAsset]:
    """The card's assets, or the documented default icon when it declares none."""
    assets = getattr(card.data, "assets", None)
    if assets:
        return list(assets)
    return list(DEFAULT_ASSETS)


def card_icon(card: CharacterCard) -> CardAsset | None:
    """The main `icon` asset, per the spec's selection rules."""
    icons = [asset for asset in card_assets(card) if asset.type == "icon"]
    if not icons:
        return None
    return next((asset for asset in icons if asset.name == "main"), icons[0])


def card_user_icon(card: CharacterCard) -> CardAsset | None:
    """The first `user_icon` asset, if the card declares one."""
    return next((asset for asset in card_assets(card) if asset.type == "user_icon"), None)


def card_group_greetings(card: CharacterCard) -> list[str]:
    """Greetings only meant for group chats (empty outside V3)."""
    greetings = getattr(card.data, "group_only_greetings", None) or []
    return [greeting for greeting in greetings if isinstance(greeting, str) and greeting.strip()]


def creator_notes_for(card: CharacterCard, language: str = "en") -> str:
    """Pick the creator notes in `language`, following the V3 fallback rules."""
    multilingual = getattr(card.data, "creator_notes_multilingual", None)
    if not multilingual:
        return card.data.creator_notes
    wanted = language.split("-")[0].lower()
    if wanted in multilingual:
        return multilingual[wanted]
    if wanted != "en" and "en" in multilingual:
        return multilingual["en"]
    if "en" not in multilingual:
        # `creator_notes` acts as the `en` note when the map omits it.
        return card.data.creator_notes
    return multilingual["en"]


def character_summary(
    character: Character,
    viewer_id: int | None = None,
    last_message_at: datetime | None = None,
) -> CharacterSummary:
    """Build the listing view, reading denormalized fields out of the card.

    `last_message_at` is viewer-relative, so callers that list characters fill it
    in from their sessions; anything else leaves it null.
    """
    data = character.card_json.get("data") or {}
    return CharacterSummary(
        id=character.id or 0,
        name=character.name,
        spec_version=character.spec_version,
        source=character.source,
        tags=[str(tag) for tag in data.get("tags") or []],
        creator=character.creator,
        character_version=character.character_version,
        is_public=character.is_public,
        is_mine=character.user_id is not None and character.user_id == viewer_id,
        has_avatar=bool(character.avatar_path),
        last_message_at=last_message_at,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


def normalize_tag(tag: str) -> str:
    """Tags are matched case-insensitively, so they are stored folded."""
    return tag.strip().lower()[:100]


async def apply_card_metadata(db: AsyncSession, character: Character, card: CharacterCard) -> None:
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


def character_detail(character: Character, viewer_id: int | None = None) -> CharacterDetail:
    card = load_card(character.card_json)
    return CharacterDetail(
        **character_summary(character, viewer_id).model_dump(),
        card=character.card_json,
        hooks=hooks_from_card_json(character.card_json),
        warnings=spec_warnings(card),
    )


def _is_version_2(value: Any) -> bool:
    version = _numeric_version(value)
    return version is not None and version == 2.0


def _numeric_version(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _describe(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors()[:5]:
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        problems.append(f"{location}: {error['msg']}")
    return "invalid character card: " + "; ".join(problems)
