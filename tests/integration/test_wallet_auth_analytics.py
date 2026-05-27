from httpx import AsyncClient
from nacl.signing import SigningKey

from app.core.security.solana_wallet import BASE58_ALPHABET
from app.shared.blockchain import BlockchainTransaction


def _b58encode(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + (encoded or "")


def _wallet() -> tuple[SigningKey, str]:
    signing_key = SigningKey.generate()
    return signing_key, _b58encode(bytes(signing_key.verify_key))


async def _wallet_login(client: AsyncClient) -> tuple[str, str]:
    signing_key, wallet_address = _wallet()
    nonce_response = await client.post(
        "/api/v1/auth/wallet/nonce", json={"wallet_address": wallet_address}
    )
    assert nonce_response.status_code == 200
    nonce = nonce_response.json()
    signature = _b58encode(signing_key.sign(nonce["message"].encode("utf-8")).signature)
    verify_response = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "wallet_address": wallet_address,
            "nonce": nonce["nonce"],
            "signature": signature,
        },
    )
    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["user"]["wallet_address"] == wallet_address
    return wallet_address, body["tokens"]["access_token"]


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@solbreach.app", "password": "admin-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def test_wallet_login_creates_wallet_owned_user(seeded_client: AsyncClient) -> None:
    wallet_address, token = await _wallet_login(seeded_client)
    me_response = await seeded_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["wallet_address"] == wallet_address


async def test_linked_wallet_enforced_during_level_setup(
    seeded_client: AsyncClient, fake_blockchain: dict[str, BlockchainTransaction]
) -> None:
    wallet_address, token = await _wallet_login(seeded_client)
    headers = {"Authorization": f"Bearer {token}"}
    level_1 = next(
        level
        for level in (await seeded_client.get("/api/v1/levels")).json()
        if level["slug"] == "level-1-fake-mint"
    )
    await seeded_client.post(f"/api/v1/levels/{level_1['id']}/start", headers=headers)

    rejected_setup = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers,
        json={"wallet_address": "WrongWallet1111111111111111111111111111111"},
    )
    assert rejected_setup.status_code == 403
    assert rejected_setup.json()["error"]["code"] == "WALLET_OWNERSHIP_REQUIRED"

    setup_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers,
        json={"wallet_address": wallet_address},
    )
    assert setup_response.status_code == 200
    challenge = setup_response.json()["challenge"]
    tx_signature = "wallet-auth-level-1-signature"
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=123,
        signers=[wallet_address],
        account_keys=challenge["required_accounts"],
    )
    submit_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": wallet_address,
            "level_session_id": setup_response.json()["level_session_id"],
        },
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["success"] is True

    forbidden_funnel = await seeded_client.get("/api/v1/analytics/funnel", headers=headers)
    assert forbidden_funnel.status_code == 403

    admin_headers = {"Authorization": f"Bearer {await _admin_token(seeded_client)}"}
    funnel_response = await seeded_client.get("/api/v1/analytics/funnel", headers=admin_headers)
    assert funnel_response.status_code == 200
    level_row = next(
        item
        for item in funnel_response.json()["data"]["levels"]
        if item["slug"] == "level-1-fake-mint"
    )
    assert level_row["started_users"] == 1
    assert level_row["setup_wallets"] == 1
    assert level_row["completed_wallets"] == 1
