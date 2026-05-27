from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_catalog_routes_default_empty(client: AsyncClient) -> None:
    for path in ["/api/v1/vulnerabilities", "/api/v1/levels", "/api/v1/labs"]:
        response = await client.get(path)

        assert response.status_code == 200
        assert response.json() == []


async def test_cors_preflight_allows_vercel_frontend(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/start",
        headers={
            "Origin": "https://solbreach.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://solbreach.vercel.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
