from httpx import AsyncClient


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@solbreach.app", "password": "admin-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def test_frontend_analytics_event_can_be_recorded_and_exported(
    seeded_client: AsyncClient,
) -> None:
    wallet_address = "AnalyticsWallet11111111111111111111111111"
    response = await seeded_client.post(
        "/api/v1/analytics/events",
        json={
            "eventName": "beta_app_entered",
            "walletAddress": wallet_address,
            "sessionId": "session-analytics-1",
            "labId": "rl1-account-substitution",
            "properties": {"sourceView": "beta-gate"},
        },
        headers={"User-Agent": "solbreach-test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["eventName"] == "beta_app_entered"
    assert body["data"]["source"] == "frontend"
    assert body["data"]["properties"] == {"sourceView": "beta-gate"}

    admin_headers = {"Authorization": f"Bearer {await _admin_token(seeded_client)}"}
    export_response = await seeded_client.get(
        "/api/v1/analytics/admin/events",
        params={"wallet_address": wallet_address},
        headers=admin_headers,
    )
    assert export_response.status_code == 200
    exported = export_response.json()["data"]
    assert len(exported) == 1
    assert exported[0]["eventName"] == "beta_app_entered"
    assert exported[0]["walletAddress"] == wallet_address
    assert exported[0]["source"] == "frontend"

    funnel_response = await seeded_client.get(
        "/api/v1/analytics/admin/funnel",
        headers=admin_headers,
    )
    assert funnel_response.status_code == 200
    assert funnel_response.json()["data"]["beta"]["appEntered"] == 1
