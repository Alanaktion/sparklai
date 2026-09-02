from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Image, Media, User


async def _make_user(db_session: AsyncSession, creator_id: int) -> User:
    user = User(name="Blob Owner", age=30, pronouns="they/them", creator_id=creator_id)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_creator_row(db_session: AsyncSession) -> int:
    from app.db.models import Creator

    creator = Creator(name="Blob Creator", password_hash="x:y")
    db_session.add(creator)
    await db_session.commit()
    await db_session.refresh(creator)
    return creator.id


async def test_get_image_serves_bytes_with_content_type(client: AsyncClient, db_session: AsyncSession):
    creator_id = await _make_creator_row(db_session)
    user = await _make_user(db_session, creator_id)
    image = Image(user_id=user.id, data=b"\x00\x01\x02", type="image/webp")
    db_session.add(image)
    await db_session.commit()
    await db_session.refresh(image)

    response = await client.get(f"/api/images/{image.id}")
    assert response.status_code == 200
    assert response.content == b"\x00\x01\x02"
    assert response.headers["content-type"] == "image/webp"
    assert "Expires" in response.headers


async def test_get_image_404(client: AsyncClient):
    response = await client.get("/api/images/999999")
    assert response.status_code == 404


async def test_patch_and_delete_image(client: AsyncClient, db_session: AsyncSession):
    creator_id = await _make_creator_row(db_session)
    user = await _make_user(db_session, creator_id)
    image = Image(user_id=user.id, data=b"x", type="image/webp", blur=False)
    db_session.add(image)
    await db_session.commit()
    await db_session.refresh(image)

    patched = await client.patch(f"/api/images/{image.id}", json={"blur": True})
    assert patched.status_code == 200

    deleted = await client.delete(f"/api/images/{image.id}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/images/{image.id}")
    assert missing.status_code == 404


async def test_get_media_serves_bytes(client: AsyncClient, db_session: AsyncSession):
    creator_id = await _make_creator_row(db_session)
    user = await _make_user(db_session, creator_id)
    media = Media(user_id=user.id, data=b"\x99", type="video/mp4")
    db_session.add(media)
    await db_session.commit()
    await db_session.refresh(media)

    response = await client.get(f"/api/media/{media.id}")
    assert response.status_code == 200
    assert response.content == b"\x99"
    assert response.headers["content-type"] == "video/mp4"


async def test_media_404_for_missing_and_delete(client: AsyncClient, db_session: AsyncSession):
    assert (await client.get("/api/media/999999")).status_code == 404

    creator_id = await _make_creator_row(db_session)
    user = await _make_user(db_session, creator_id)
    media = Media(user_id=user.id, data=b"x", type="video/mp4")
    db_session.add(media)
    await db_session.commit()
    await db_session.refresh(media)

    assert (await client.delete(f"/api/media/{media.id}")).status_code == 204
    assert (await client.get(f"/api/media/{media.id}")).status_code == 404
