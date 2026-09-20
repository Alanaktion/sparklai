"""World book stacking and precedence: PLAN §4.4."""

import copy
from collections.abc import AsyncIterator

from httpx import AsyncClient

from sparklchat.models.card import CharacterBook, TavernCardV2
from sparklchat.services.lorebook import select_stacked_entries
from sparklchat.services.prompts import HistoryTurn, PromptContext, build_prompt
from sparklchat.services.providers import ChatMessage

CONTEXT = PromptContext(character_name="Haruhi", user_name="Ash")
HISTORY = ["the brigade and the club"]


def entry(**overrides) -> dict:
    values: dict = {
        "keys": ["brigade"],
        "content": "content",
        "enabled": True,
        "insertion_order": 10,
        "extensions": {},
    }
    values.update(overrides)
    return values


def book(entries: list[dict], **overrides) -> CharacterBook:
    values: dict = {"extensions": {}, "entries": entries}
    values.update(overrides)
    return CharacterBook.model_validate(values)


def contents(matched) -> list[str]:
    return [item.content for item in matched.all]


# --- stacking ---------------------------------------------------------------


def test_world_entries_are_injected_when_a_key_matches() -> None:
    world = book([entry(content="WORLD")])
    assert contents(select_stacked_entries(None, world, HISTORY)) == ["WORLD"]


def test_character_book_takes_precedence_on_a_key_collision() -> None:
    character = book([entry(content="CHAR")])
    world = book([entry(content="WORLD")])
    assert contents(select_stacked_entries(character, world, HISTORY)) == ["CHAR"]


def test_non_colliding_world_entries_are_kept() -> None:
    character = book([entry(keys=["brigade"], content="CHAR")])
    world = book(
        [
            entry(keys=["brigade"], content="DUP"),
            entry(keys=["club"], content="WORLD"),
        ]
    )
    assert contents(select_stacked_entries(character, world, HISTORY)) == ["CHAR", "WORLD"]


def test_precedence_ignores_key_case() -> None:
    character = book([entry(keys=["BRIGADE"], content="CHAR")])
    world = book([entry(keys=["brigade"], content="WORLD")])
    assert contents(select_stacked_entries(character, world, HISTORY)) == ["CHAR"]


def test_world_book_only_matches_when_its_keys_appear() -> None:
    world = book([entry(keys=["trombone"], content="WORLD")])
    assert contents(select_stacked_entries(None, world, HISTORY)) == []


def test_entries_interleave_by_insertion_order_across_both_books() -> None:
    character = book([entry(keys=["brigade"], content="CHAR-LATE", insertion_order=20)])
    world = book([entry(keys=["club"], content="WORLD-EARLY", insertion_order=5)])
    assert contents(select_stacked_entries(character, world, HISTORY)) == [
        "WORLD-EARLY",
        "CHAR-LATE",
    ]


def test_each_book_can_be_switched_off() -> None:
    character = book([entry(content="CHAR")])
    world = book([entry(content="WORLD")])

    # Book off means its entries are not matched, so its keys do not suppress.
    assert contents(
        select_stacked_entries(character, world, HISTORY, use_character_book=False)
    ) == ["WORLD"]
    assert contents(select_stacked_entries(character, world, HISTORY, use_world_book=False)) == [
        "CHAR"
    ]
    assert (
        contents(
            select_stacked_entries(
                character, world, HISTORY, use_character_book=False, use_world_book=False
            )
        )
        == []
    )


def test_world_book_keeps_its_own_token_budget() -> None:
    world = book(
        [
            entry(keys=["brigade"], content="a" * 40, insertion_order=1, priority=1),
            entry(keys=["club"], content="b" * 40, insertion_order=2, priority=50),
        ],
        token_budget=12,
    )
    assert contents(select_stacked_entries(None, world, HISTORY)) == ["b" * 40]


def test_constant_world_entries_never_collide() -> None:
    character = book([entry(keys=[], constant=True, content="CHAR-CONSTANT")])
    world = book([entry(keys=[], constant=True, content="WORLD-CONSTANT")])
    assert contents(select_stacked_entries(character, world, HISTORY)) == [
        "CHAR-CONSTANT",
        "WORLD-CONSTANT",
    ]


# --- prompt assembly --------------------------------------------------------


def make_card(**overrides) -> TavernCardV2:
    data: dict = {
        "name": "Haruhi",
        "description": "A blunt student.",
        "first_mes": "Hi!",
        "mes_example": "",
    }
    data.update(overrides)
    return TavernCardV2.model_validate(
        {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}
    )


def system_text(messages: list[ChatMessage]) -> str:
    return messages[0].content


def test_build_prompt_injects_world_entries() -> None:
    card = make_card()
    world = book([entry(content="WORLD-MARKER")])
    prompt = build_prompt(
        card,
        [HistoryTurn(role="user", content="brigade")],
        context=CONTEXT,
        world_book=world,
    )
    assert "WORLD-MARKER" in system_text(prompt)


def test_build_prompt_suppresses_collided_world_entries() -> None:
    card = make_card(
        character_book={
            "extensions": {},
            "entries": [{"keys": ["brigade"], "content": "CHAR-MARKER", "extensions": {}}],
        }
    )
    world = book([entry(content="WORLD-MARKER")])
    prompt = build_prompt(
        card,
        [HistoryTurn(role="user", content="brigade")],
        context=CONTEXT,
        world_book=world,
    )
    assert "CHAR-MARKER" in system_text(prompt)
    assert "WORLD-MARKER" not in system_text(prompt)


def test_build_prompt_world_book_can_be_switched_off() -> None:
    card = make_card()
    world = book([entry(content="WORLD-MARKER")])
    history = [HistoryTurn(role="user", content="brigade")]

    assert "WORLD-MARKER" in system_text(
        build_prompt(card, history, context=CONTEXT, world_book=world)
    )
    assert "WORLD-MARKER" not in system_text(
        build_prompt(card, history, context=CONTEXT, world_book=world, use_world_book=False)
    )


# --- API --------------------------------------------------------------------

WORLD_BOOK = {
    "name": "World",
    "scan_depth": 4,
    "token_budget": 512,
    "recursive_scanning": False,
    "extensions": {"world_ext": {"keep": True}},
    "entries": [
        {
            "keys": ["brigade"],
            "content": "The brigade meets on Wednesdays.",
            "enabled": True,
            "insertion_order": 1,
            "extensions": {"entry_ext": "keep"},
        }
    ],
}


class StubClient:
    def __init__(self, reply: str = "ok") -> None:
        self.prompts: list[list[ChatMessage]] = []
        self._reply = reply

    async def complete(self, messages) -> str:
        self.prompts.append(list(messages))
        return self._reply

    async def stream(self, messages) -> AsyncIterator[str]:
        self.prompts.append(list(messages))
        yield self._reply


async def make_provider(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/providers",
        json={
            "name": "Test provider",
            "provider_type": "openai",
            "base_url": "https://api.example/v1",
            "api_key": "sk-test",
            "model": "test-model",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    provider = response.json()
    await client.patch(
        "/api/settings", json={"default_provider_id": provider["id"]}, headers=headers
    )
    return provider


async def make_character(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def make_session(client: AsyncClient, headers: dict[str, str], character_id: int) -> dict:
    response = await client.post(
        f"/api/characters/{character_id}/sessions", json={}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def simple_card() -> dict:
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Haruhi",
            "description": "A blunt student.",
            "first_mes": "Hi!",
            "mes_example": "",
            "extensions": {},
        },
    }


async def test_world_book_is_absent_by_default(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    assert (await client.get("/api/settings/world-book", headers=auth_headers)).json() is None


async def test_world_book_round_trips(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    put = await client.put("/api/settings/world-book", json=WORLD_BOOK, headers=auth_headers)
    assert put.status_code == 200, put.text
    assert put.json() == WORLD_BOOK

    fetched = await client.get("/api/settings/world-book", headers=auth_headers)
    # Unknown keys at book and entry level survive the round trip.
    assert fetched.json() == WORLD_BOOK

    settings = await client.get("/api/settings", headers=auth_headers)
    assert settings.json()["world_book"] == WORLD_BOOK

    removed = await client.delete("/api/settings/world-book", headers=auth_headers)
    assert removed.status_code == 204
    assert (await client.get("/api/settings/world-book", headers=auth_headers)).json() is None
    assert (await client.get("/api/settings", headers=auth_headers)).json()["world_book"] is None


async def test_world_book_is_per_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    await client.put("/api/settings/world-book", json=WORLD_BOOK, headers=auth_headers)
    other = await login_as("misty@example.com")
    assert (await client.get("/api/settings/world-book", headers=other)).json() is None


async def test_world_book_rejects_a_broken_entry(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    broken = copy.deepcopy(WORLD_BOOK)
    broken["entries"][0]["keys"] = 5
    response = await client.put("/api/settings/world-book", json=broken, headers=auth_headers)
    assert response.status_code == 422
    assert "Invalid world book" in response.json()["detail"]


async def test_world_book_accepts_a_lorebook_v3_envelope(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    enveloped = {"spec": "lorebook_v3", "data": WORLD_BOOK}
    put = await client.put("/api/settings/world-book", json=enveloped, headers=auth_headers)
    assert put.status_code == 200, put.text
    # The envelope is unwrapped so storage stays book-shaped.
    assert put.json() == WORLD_BOOK
    assert (await client.get("/api/settings/world-book", headers=auth_headers)).json() == WORLD_BOOK


async def test_sessions_default_to_the_world_book_on(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    character = await make_character(client, auth_headers, simple_card())
    session = await make_session(client, auth_headers, character["id"])
    assert session["use_world_book"] is True

    patched = await client.patch(
        f"/api/sessions/{session['id']}",
        json={"use_world_book": False},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["use_world_book"] is False


async def test_world_entry_reaches_the_prompt_and_can_be_toggled(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    await client.put("/api/settings/world-book", json=WORLD_BOOK, headers=auth_headers)
    character = await make_character(client, auth_headers, simple_card())
    session = await make_session(client, auth_headers, character["id"])

    stub = StubClient()
    monkeypatch.setattr("sparklchat.api.chat.build_client", lambda config: stub)

    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "tell me about the brigade"},
        headers=auth_headers,
    )
    assert "The brigade meets on Wednesdays." in stub.prompts[-1][0].content

    await client.patch(
        f"/api/sessions/{session['id']}",
        json={"use_world_book": False},
        headers=auth_headers,
    )
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "again"},
        headers=auth_headers,
    )
    assert "The brigade meets on Wednesdays." not in stub.prompts[-1][0].content


async def test_character_book_wins_over_the_world_book_end_to_end(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    await client.put("/api/settings/world-book", json=WORLD_BOOK, headers=auth_headers)

    card = copy.deepcopy(simple_card())
    card["data"]["character_book"] = {
        "extensions": {},
        "entries": [
            {
                "keys": ["brigade"],
                "content": "The brigade is fictional.",
                "extensions": {},
            }
        ],
    }
    character = await make_character(client, auth_headers, card)
    session = await make_session(client, auth_headers, character["id"])

    stub = StubClient()
    monkeypatch.setattr("sparklchat.api.chat.build_client", lambda config: stub)
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "the brigade"},
        headers=auth_headers,
    )

    system = stub.prompts[-1][0].content
    assert "The brigade is fictional." in system
    assert "The brigade meets on Wednesdays." not in system
