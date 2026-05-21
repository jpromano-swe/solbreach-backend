from httpx import AsyncClient


async def test_register_login_and_me(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "researcher_one",
            "email": "researcher@example.com",
            "password": "strong-password",
        },
    )

    assert register_response.status_code == 201
    register_data = register_response.json()
    assert register_data["user"]["email"] == "researcher@example.com"
    assert register_data["tokens"]["token_type"] == "bearer"

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "researcher@example.com", "password": "strong-password"},
    )

    assert login_response.status_code == 200
    access_token = login_response.json()["tokens"]["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["username"] == "researcher_one"
