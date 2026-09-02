from httpx import AsyncClient


async def test_signup_creates_creator_without_leaking_password_hash(client: AsyncClient):
    response = await client.post("/api/creators", json={"name": "Alice", "pin": "1234"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert data["pronouns"] == "they/them"
    assert "password_hash" not in data


async def test_me_is_null_when_logged_out(client: AsyncClient):
    response = await client.get("/api/creators/me")
    assert response.status_code == 200
    assert response.json() is None


async def test_login_sets_cookie_and_me_reflects_it(client: AsyncClient):
    signup = await client.post("/api/creators", json={"name": "Bob", "pin": "5678"})
    creator_id = signup.json()["id"]

    wrong_pin = await client.post(f"/api/creators/{creator_id}", json={"pin": "0000"})
    assert wrong_pin.status_code == 401

    login = await client.post(f"/api/creators/{creator_id}", json={"pin": "5678"})
    assert login.status_code == 200
    assert "creator_session" in login.cookies

    me = await client.get("/api/creators/me")
    assert me.status_code == 200
    assert me.json()["id"] == creator_id


async def test_logout_clears_session(client: AsyncClient):
    signup = await client.post("/api/creators", json={"name": "Carol", "pin": "1111"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "1111"})

    logout = await client.delete("/api/creators/session")
    assert logout.status_code == 200

    me = await client.get("/api/creators/me")
    assert me.json() is None


async def test_update_profile_requires_auth(client: AsyncClient):
    response = await client.patch("/api/creators/me", json={"bio": "hi"})
    assert response.status_code == 401


async def test_update_profile_only_touches_sent_fields(client: AsyncClient):
    signup = await client.post(
        "/api/creators", json={"name": "Dana", "pin": "2222", "pronouns": "she/her"}
    )
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "2222"})

    updated = await client.patch("/api/creators/me", json={"bio": "Hello world"})
    assert updated.status_code == 200
    data = updated.json()
    assert data["bio"] == "Hello world"
    assert data["pronouns"] == "she/her"  # untouched
