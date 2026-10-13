from httpx import AsyncClient


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@solbreach.app", "password": "admin-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def test_waitlist_create_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/waitlist",
        json={
            "name_or_handle": "  juanromano  ",
            "contact": "Juan@Example.com",
            "is_solana_dev": True,
            "interests": ["learn_solana_security", "rust_developer"],
            "community_or_org": " Turbin3 ",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["already_joined"] is False
    assert body["data"]["name_or_handle"] == "juanromano"
    assert body["data"]["contact"] == "juan@example.com"
    assert body["data"]["contact_type"] == "email"
    assert body["data"]["is_solana_dev"] is True
    assert body["data"]["interests"] == ["learn_solana_security", "rust_developer"]
    assert body["data"]["community_or_org"] == "Turbin3"


async def test_waitlist_duplicate_upsert_unions_interests(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/waitlist",
        json={
            "name_or_handle": "juanromano",
            "contact": "juan@example.com",
            "is_solana_dev": True,
            "interests": ["learn_solana_security"],
            "community_or_org": "Turbin3",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/waitlist",
        json={
            "name_or_handle": "juan romano",
            "contact": "JUAN@example.com",
            "is_solana_dev": False,
            "interests": ["learn_solana_security", "partner_interest"],
            "community_or_org": "",
        },
    )

    assert second.status_code == 200
    body = second.json()["data"]
    assert body["already_joined"] is True
    assert body["name_or_handle"] == "juan romano"
    assert body["is_solana_dev"] is False
    assert body["community_or_org"] == "Turbin3"
    assert body["interests"] == ["learn_solana_security", "partner_interest"]


async def test_waitlist_rejects_invalid_interests_and_blank_contact(client: AsyncClient) -> None:
    blank_contact = await client.post(
        "/api/v1/waitlist",
        json={
            "name_or_handle": "juanromano",
            "contact": "   ",
            "is_solana_dev": True,
            "interests": ["learn_solana_security"],
        },
    )
    assert blank_contact.status_code == 422
    assert blank_contact.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_interest = await client.post(
        "/api/v1/waitlist",
        json={
            "name_or_handle": "juanromano",
            "contact": "@juan",
            "is_solana_dev": True,
            "interests": ["wrong_interest"],
        },
    )
    assert invalid_interest.status_code == 422
    assert invalid_interest.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_waitlist_admin_list_requires_admin_and_supports_filters(
    seeded_client: AsyncClient,
) -> None:
    for payload in [
        {
            "name_or_handle": "alice",
            "contact": "alice@example.com",
            "is_solana_dev": True,
            "interests": ["rust_developer", "first_flight_audits"],
        },
        {
            "name_or_handle": "bob",
            "contact": "@bobtg",
            "is_solana_dev": False,
            "interests": ["community_or_cohort"],
        },
    ]:
        response = await seeded_client.post("/api/v1/waitlist", json=payload)
        assert response.status_code in (200, 201)

    forbidden = await seeded_client.get("/api/v1/waitlist")
    assert forbidden.status_code == 401

    headers = {"Authorization": f"Bearer {await _admin_token(seeded_client)}"}
    response = await seeded_client.get(
        "/api/v1/waitlist?is_solana_dev=true&interest=rust_developer",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["name_or_handle"] == "alice"
    assert body["data"][0]["already_joined"] is False
