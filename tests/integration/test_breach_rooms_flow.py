from httpx import AsyncClient

from app.modules.breach_rooms.infrastructure.github.client import (
    GitHubBreachRoomClient,
    GitHubPullRequestError,
    PullRequestResult,
)


async def _auth_headers(client: AsyncClient, email: str = "breach@example.com") -> dict[str, str]:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "username": email.split("@")[0].replace(".", "_"),
            "email": email,
            "password": "strong-password",
        },
    )
    assert register.status_code == 201
    token = register.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _report_markdown() -> str:
    return """
# Vault ledger drift

## Finding Summary
- Category: Accounting
- Severity: High
- Likelihood: Medium
- Affected file or instruction: programs/vault_ledger/src/lib.rs

## Description
Normal protocol behavior should keep the vault ledger and token vault balance aligned.
The vulnerable behavior accepts a ledger update without checking the vault relationship.

## Root Cause
The route trusts caller-provided account relationships instead of validating stored fields.

## Proof of Impact
An attacker can move protocol state so accounting indicates collateral is present when the
canonical vault does not contain the matching balance.

## Evidence
- Source reference: programs/vault_ledger/src/lib.rs:42
- Test or transaction evidence: local reproduction
- Account/state delta: ledger increases while vault balance stays unchanged

## Proof of Concept
Submit the mismatched account pair and observe the accepted ledger state transition.

## Recommended Mitigation
Validate the market, vault, mint, and position relationship before mutating state.

## Notes
No extra assumptions.
""".strip()


async def test_breach_rooms_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/breach-rooms")
    assert response.status_code == 401


async def test_breach_room_catalog_and_detail_are_authenticated(client: AsyncClient) -> None:
    headers = await _auth_headers(client)

    list_response = await client.get("/api/v1/breach-rooms", headers=headers)
    assert list_response.status_code == 200
    rooms = list_response.json()
    assert rooms[0]["id"] == "breach-room-1"
    assert rooms[0]["displayName"] == "Breach Room 1: Vault Ledger"
    assert rooms[0]["repositoryUrl"] == "https://github.com/jpromano-swe/solbreach-breachrooms"

    detail = await client.get("/api/v1/breach-rooms/breach-room-1", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["installUrl"] == "https://github.com/solanabr/auditor-skill"
    assert detail.json()["auditCommand"] == "/auditor:audit-cycle"


async def test_submit_breach_room_creates_review_pr_metadata(
    client: AsyncClient, monkeypatch
) -> None:
    async def fake_create_submission_pr(self, draft):  # noqa: ANN001, ANN202
        assert draft.branch.startswith("submission/breach-room-1/")
        assert draft.file_path.startswith("submissions/breach-room-1/")
        assert draft.title == "[Breach Room 1] High - Vault ledger drift"
        assert "- Room: breach-room-1" in draft.body
        assert "## Report" in draft.content
        return PullRequestResult(url="https://github.com/example/repo/pull/7", number=7)

    monkeypatch.setattr(
        GitHubBreachRoomClient,
        "create_submission_pr",
        fake_create_submission_pr,
    )
    headers = await _auth_headers(client, "breach-submit@example.com")

    response = await client.post(
        "/api/v1/breach-rooms/breach-room-1/submissions",
        headers=headers,
        json={
            "title": "Vault ledger drift",
            "category": "Accounting",
            "severity": "High",
            "likelihood": "Medium",
            "sourceReference": "programs/vault_ledger/src/lib.rs:42",
            "reportMarkdown": _report_markdown(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert body["reviewState"] == "reviewing"
    assert body["prUrl"] == "https://github.com/example/repo/pull/7"
    assert body["prCreationStatus"] == "created"

    mine = await client.get(
        "/api/v1/breach-rooms/breach-room-1/submissions/me",
        headers=headers,
    )
    assert mine.status_code == 200
    assert mine.json()[0]["title"] == "Vault ledger drift"
    assert mine.json()[0]["reportMarkdown"] == _report_markdown()

    results = await client.get("/api/v1/breach-rooms/breach-room-1/results/me", headers=headers)
    assert results.status_code == 200
    assert results.json()["status"] == "reviewing"
    assert results.json()["xpEarned"] == 0


async def test_submit_breach_room_preserves_submission_when_pr_creation_fails(
    client: AsyncClient,
    monkeypatch,
) -> None:
    async def fake_create_submission_pr(self, draft):  # noqa: ANN001, ANN202, ARG001
        raise GitHubPullRequestError("BREACH_ROOMS_GITHUB_TOKEN is required")

    monkeypatch.setattr(
        GitHubBreachRoomClient,
        "create_submission_pr",
        fake_create_submission_pr,
    )
    headers = await _auth_headers(client, "breach-failed-pr@example.com")

    response = await client.post(
        "/api/v1/breach-rooms/breach-room-1/submissions",
        headers=headers,
        json={
            "title": "Vault ledger drift",
            "category": "Accounting",
            "severity": "High",
            "likelihood": "Medium",
            "sourceReference": "programs/vault_ledger/src/lib.rs:42",
            "reportMarkdown": _report_markdown(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["prUrl"] is None
    assert body["prCreationStatus"] == "failed"
    assert "TOKEN" in body["prCreationError"]

    mine = await client.get(
        "/api/v1/breach-rooms/breach-room-1/submissions/me",
        headers=headers,
    )
    assert mine.status_code == 200
    assert mine.json()[0]["prCreationStatus"] == "failed"
