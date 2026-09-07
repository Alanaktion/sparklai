from httpx import AsyncClient

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Placeholder",
        "description": "[Age: 25]",
        "personality": "",
        "scenario": "",
        "first_mes": "",
        "mes_example": "",
        "creator_notes": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "alternate_greetings": [],
        "tags": [],
        "character_version": "",
        "avatar": "",
        "creator": "",
        "extensions": {},
    },
}


async def _login_new_creator(client: AsyncClient, name: str = "Relationship Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient, name: str) -> int:
    card = {**CARD, "data": {**CARD["data"], "name": name}}
    imported = await client.post("/api/import-character", json=card)
    return imported.json()["id"]


async def _relationships_for(client: AsyncClient, user_id: int) -> list[dict]:
    response = await client.get(f"/api/users/{user_id}")
    return response.json()["relationships"]


async def test_create_relationship_is_mutual_by_default(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    response = await client.post(
        f"/api/users/{alice}/relationships",
        json={"related_user_id": bob, "relationship_type": "best friend", "description": "since college"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == bob
    assert body["relationship_type"] == "best friend"
    assert isinstance(body["relationship_id"], int)

    alice_rels = await _relationships_for(client, alice)
    assert [r["id"] for r in alice_rels] == [bob]

    bob_rels = await _relationships_for(client, bob)
    assert [r["id"] for r in bob_rels] == [alice]
    assert bob_rels[0]["relationship_type"] == "best friend"
    # The reverse row is its own row, not the same one.
    assert bob_rels[0]["relationship_id"] != body["relationship_id"]


async def test_create_relationship_with_asymmetric_reverse_label(client: AsyncClient):
    await _login_new_creator(client)
    child = await _create_ai_user(client, "Child")
    parent = await _create_ai_user(client, "Parent")

    response = await client.post(
        f"/api/users/{child}/relationships",
        json={
            "related_user_id": parent,
            "relationship_type": "parent",
            "reverse_relationship_type": "child",
        },
    )
    assert response.status_code == 201
    assert response.json()["relationship_type"] == "parent"

    child_rels = await _relationships_for(client, child)
    assert child_rels[0]["relationship_type"] == "parent"  # "Parent is my parent"

    parent_rels = await _relationships_for(client, parent)
    assert parent_rels[0]["relationship_type"] == "child"  # "Child is my child"


async def test_create_relationship_non_mutual_only_creates_one_direction(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    response = await client.post(
        f"/api/users/{alice}/relationships",
        json={"related_user_id": bob, "relationship_type": "admires", "mutual": False},
    )
    assert response.status_code == 201

    assert len(await _relationships_for(client, alice)) == 1
    assert len(await _relationships_for(client, bob)) == 0


async def test_create_relationship_rejects_self(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")

    response = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": alice}
    )
    assert response.status_code == 400


async def test_create_relationship_rejects_other_creators_user(client: AsyncClient):
    await _login_new_creator(client, "Creator A")
    alice = await _create_ai_user(client, "Alice")

    await _login_new_creator(client, "Creator B")
    carol = await _create_ai_user(client, "Carol")

    response = await client.post(
        f"/api/users/{carol}/relationships", json={"related_user_id": alice}
    )
    assert response.status_code == 400


async def test_create_relationship_rejects_duplicate(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    first = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob, "mutual": False}
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob, "mutual": False}
    )
    assert second.status_code == 409


async def test_create_relationship_requires_ownership_of_source_user(client: AsyncClient):
    await _login_new_creator(client, "Creator A")
    alice = await _create_ai_user(client, "Alice")

    await _login_new_creator(client, "Creator B")
    response = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": alice}
    )
    assert response.status_code == 403


async def test_update_relationship_only_affects_one_direction(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    created = await client.post(
        f"/api/users/{alice}/relationships",
        json={"related_user_id": bob, "relationship_type": "friend"},
    )
    relationship_id = created.json()["relationship_id"]

    response = await client.patch(
        f"/api/users/{alice}/relationships/{relationship_id}",
        json={"relationship_type": "best friend"},
    )
    assert response.status_code == 200
    assert response.json()["relationship_type"] == "best friend"

    bob_rels = await _relationships_for(client, bob)
    assert bob_rels[0]["relationship_type"] == "friend"  # unaffected by Alice's-side edit


async def test_update_relationship_wrong_owner_rejected(client: AsyncClient):
    await _login_new_creator(client, "Creator A")
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")
    created = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob}
    )
    relationship_id = created.json()["relationship_id"]

    await _login_new_creator(client, "Creator B")
    response = await client.patch(
        f"/api/users/{alice}/relationships/{relationship_id}",
        json={"relationship_type": "rival"},
    )
    assert response.status_code == 403


async def test_update_relationship_mismatched_user_id_rejected(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")
    carol = await _create_ai_user(client, "Carol")

    created = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob, "mutual": False}
    )
    relationship_id = created.json()["relationship_id"]

    # `relationship_id` belongs to Alice, not Carol.
    response = await client.patch(
        f"/api/users/{carol}/relationships/{relationship_id}",
        json={"relationship_type": "rival"},
    )
    assert response.status_code == 404


async def test_delete_relationship_mutual_removes_both_directions(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    created = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob}
    )
    relationship_id = created.json()["relationship_id"]

    response = await client.delete(f"/api/users/{alice}/relationships/{relationship_id}")
    assert response.status_code == 204

    assert await _relationships_for(client, alice) == []
    assert await _relationships_for(client, bob) == []


async def test_delete_relationship_non_mutual_leaves_reverse_intact(client: AsyncClient):
    await _login_new_creator(client)
    alice = await _create_ai_user(client, "Alice")
    bob = await _create_ai_user(client, "Bob")

    created = await client.post(
        f"/api/users/{alice}/relationships", json={"related_user_id": bob}
    )
    relationship_id = created.json()["relationship_id"]

    response = await client.delete(
        f"/api/users/{alice}/relationships/{relationship_id}", params={"mutual": "false"}
    )
    assert response.status_code == 204

    assert await _relationships_for(client, alice) == []
    assert len(await _relationships_for(client, bob)) == 1  # Bob -> Alice row untouched
