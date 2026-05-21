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
