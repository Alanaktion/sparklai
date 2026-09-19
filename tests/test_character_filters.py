"""Character listing filters and the denormalized tag rows."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.character import CharacterTag


def card(name: str, *, tags: list[str], creator: str = "", version: str = "") -> dict:
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": "A student.",
            "personality": "Bold.",
            "scenario": "The club room.",
            "first_mes": "Hi!",
            "mes_example": "",
            "tags": tags,
            "creator": creator,
            "character_version": version,
            "extensions": {},
        },
    }


async def create(client: AsyncClient, headers: dict[str, str], payload: dict) -> dict:
    response = await client.post("/api/characters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def names(client: AsyncClient, headers: dict[str, str], **params) -> list[str]:
    response = await client.get("/api/characters", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()]


async def seed(client: AsyncClient, headers: dict[str, str]) -> None:
    await create(
        client, headers, card("Haruhi", tags=["Anime", "School"], creator="tests", version="1.1")
    )
    await create(
        client, headers, card("Mikuru", tags=["anime", "Moe"], creator="other", version="2.0")
    )
    await create(client, headers, card("Yuki", tags=["Alien"], creator="tests", version="2.0"))


async def test_filters_by_name(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await seed(client, auth_headers)
    assert await names(client, auth_headers, q="miku") == ["Mikuru"]


async def test_filters_by_tag_ignoring_case(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await seed(client, auth_headers)

    assert await names(client, auth_headers, tags="ANIME") == ["Haruhi", "Mikuru"]
    assert await names(client, auth_headers, tags="alien") == ["Yuki"]


async def test_filters_by_any_of_several_tags(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await seed(client, auth_headers)

    assert await names(client, auth_headers, tags=["alien", "moe"]) == ["Mikuru", "Yuki"]


async def test_filters_by_creator(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await seed(client, auth_headers)

    assert await names(client, auth_headers, creator="tests") == ["Haruhi", "Yuki"]
    # Creator matching is case-insensitive and partial.
    assert await names(client, auth_headers, creator="THER") == ["Mikuru"]


async def test_filters_by_character_version(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await seed(client, auth_headers)
    assert await names(client, auth_headers, character_version="2.0") == ["Mikuru", "Yuki"]


async def test_filters_combine(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await seed(client, auth_headers)

    assert await names(client, auth_headers, tags="anime", creator="tests") == ["Haruhi"]


async def seed_versions(client: AsyncClient, headers: dict[str, str]) -> None:
    await create(client, headers, card("Alpha", tags=[], version="3.0"))
    await create(client, headers, card("Beta", tags=[], version="1.0"))
    await create(client, headers, card("Gamma", tags=[], version="2.0"))


async def test_lists_by_name_by_default(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await seed_versions(client, auth_headers)
    assert await names(client, auth_headers) == ["Alpha", "Beta", "Gamma"]


async def test_sorts_by_character_version(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await seed_versions(client, auth_headers)
    assert await names(client, auth_headers, sort="character_version") == [
        "Beta",
        "Gamma",
        "Alpha",
    ]


async def test_sorts_by_most_recently_created(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await seed_versions(client, auth_headers)
    assert await names(client, auth_headers, sort="created") == ["Gamma", "Beta", "Alpha"]


async def test_rejects_an_unknown_sort(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/characters", params={"sort": "weird"}, headers=auth_headers)
    assert response.status_code == 422


async def test_tags_are_stored_lowercased_and_keep_original_case_in_the_card(
    client: AsyncClient, auth_headers: dict[str, str], engine: AsyncEngine
) -> None:
    created = await create(client, auth_headers, card("Haruhi", tags=["Anime", "School"]))
    assert created["tags"] == ["Anime", "School"]

    async with AsyncSession(engine) as session:
        rows = (
            await session.exec(
                select(CharacterTag).where(CharacterTag.character_id == created["id"])
            )
        ).all()

    assert sorted(row.tag for row in rows) == ["anime", "school"]


async def test_duplicate_tags_are_collapsed(
    client: AsyncClient, auth_headers: dict[str, str], engine: AsyncEngine
) -> None:
    created = await create(client, auth_headers, card("Haruhi", tags=["Anime", "anime", " ANIME "]))

    async with AsyncSession(engine) as session:
        rows = (
            await session.exec(
                select(CharacterTag).where(CharacterTag.character_id == created["id"])
            )
        ).all()

    assert [row.tag for row in rows] == ["anime"]


async def test_editing_a_card_rebuilds_its_tags(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers, card("Haruhi", tags=["Anime"]))
    assert await names(client, auth_headers, tags="anime") == ["Haruhi"]

    edited = card("Haruhi", tags=["Alien"], creator="changed", version="9.9")
    response = await client.patch(
        f"/api/characters/{created['id']}", json={"card": edited}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["creator"] == "changed"
    assert response.json()["character_version"] == "9.9"

    assert await names(client, auth_headers, tags="anime") == []
    assert await names(client, auth_headers, tags="alien") == ["Haruhi"]
    assert await names(client, auth_headers, creator="changed") == ["Haruhi"]


async def test_deleting_a_character_removes_its_tags(
    client: AsyncClient, auth_headers: dict[str, str], engine: AsyncEngine
) -> None:
    created = await create(client, auth_headers, card("Haruhi", tags=["Anime"]))

    assert (
        await client.delete(f"/api/characters/{created['id']}", headers=auth_headers)
    ).status_code == 204

    async with AsyncSession(engine) as session:
        rows = (await session.exec(select(CharacterTag))).all()

    assert rows == []


async def test_filters_are_scoped_to_the_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    await seed(client, auth_headers)
    other = await login_as("misty@example.com")

    assert await names(client, other, tags="anime") == []
    assert await names(client, other) == []
