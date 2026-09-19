"""Serving the built Svelte SPA alongside the API."""

from httpx import AsyncClient

SPA_MARKER = "Sparkl Chat SPA"
# Browsers send this header; the SPA fallback only applies to navigation
# requests, so non-HTML callers get honest 404s for missing files.
NAVIGATION = {"Accept": "text/html"}


async def test_index_is_served(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/", headers=NAVIGATION)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert SPA_MARKER in response.text


async def test_deep_links_fall_back_to_index(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/characters/5", headers=NAVIGATION)
    assert response.status_code == 200
    assert SPA_MARKER in response.text


async def test_built_assets_are_served(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/_app/immutable/app.js")
    assert response.status_code == 200
    assert "sparklchat" in response.text


async def test_robots_txt_is_served(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/robots.txt")
    assert response.status_code == 200


async def test_missing_assets_do_not_fall_back_to_html(spa_client: AsyncClient) -> None:
    # A missing asset must 404 rather than quietly receive the SPA shell, so
    # `fetch()` mistakes surface loudly.
    response = await spa_client.get("/_app/immutable/missing.js")
    assert response.status_code == 404


async def test_api_routes_take_precedence_over_the_spa(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/api/health", headers=NAVIGATION)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unknown_api_paths_return_json_not_html(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/api/does-not-exist", headers=NAVIGATION)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


async def test_api_paths_never_serve_the_spa(spa_client: AsyncClient) -> None:
    for method in ("get", "post", "put", "patch", "delete"):
        response = await getattr(spa_client, method)("/api/nope", headers=NAVIGATION)
        assert response.headers["content-type"].startswith("application/json"), method
        assert response.status_code == 404, method


async def test_openapi_is_still_reachable(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Sparkl Chat"
