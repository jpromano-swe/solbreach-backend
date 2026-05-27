# SolBreach Frontend Integration: Level 1

This document is the frontend contract for Level 1, "The Illusionist".

Base URL for the deployed demo backend:

```txt
http://56.125.190.174:8000
```

All protected endpoints require:

```txt
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Level Identity

Seeded Level 1:

```json
{
  "id": "96d2111d-bb01-5a1b-9536-57331fed473e",
  "slug": "level-1-fake-mint",
  "title": "Level 1: The Illusionist",
  "network": "devnet",
  "xp_reward": 100
}
```

Seeded Level 2 unlock target:

```json
{
  "id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
  "slug": "level-2-authority-spoofing"
}
```

## Complete Gameplay Flow

1. Connect wallet

   Frontend action: user connects a Solana wallet through wallet adapter.

   Frontend state transition: `disconnected` -> `wallet_connected`.

   Required wallet network: Solana devnet.

2. Start Level 1

   Frontend action: call `POST /api/v1/levels/{id}/start`.

   Backend response: returns level metadata, active session, and execution metadata.

   Frontend state transition: `wallet_connected` -> `level_started`.

3. Setup challenge

   Frontend action: call `POST /api/v1/levels/{id}/setup` with the connected wallet address.

   Backend response: returns deterministic session-bound challenge accounts.

   Frontend state transition: `level_started` -> `setup_ready`.

4. Build exploit transaction

   Frontend action: build a devnet transaction from the challenge data.

   The transaction must be signed by the connected wallet and must include the required challenge accounts returned from setup.

   Frontend state transition: `setup_ready` -> `tx_pending`.

5. Sign and submit transaction

   Frontend action: call wallet adapter signing, then submit the signed transaction to devnet RPC.

   Frontend captures the resulting transaction signature.

   Frontend state transition: `tx_pending` -> `tx_confirmed`.

6. Submit proof

   Frontend action: call `POST /api/v1/levels/{id}/submit`.

   Backend response: verifies transaction outcome, updates session, awards XP, unlocks Level 2.

   Frontend state transition: `tx_confirmed` -> `verification_pending` -> `verified` or `failed`.

7. Refresh status

   Frontend action: call `GET /api/v1/levels/{id}/status`.

   Expected Level 1 state after success: `completed`.

   Expected Level 2 state after success: `available`.

## Endpoint Contracts

### Start Level

```txt
POST /api/v1/levels/{level_id}/start
```

Auth: required.

Request body: none.

Success status: `201 Created`.

Example response:

```json
{
  "level": {
    "id": "96d2111d-bb01-5a1b-9536-57331fed473e",
    "slug": "level-1-fake-mint",
    "title": "Level 1: The Illusionist",
    "description": "Exploit a fake mint path where counterfeit token accounts and vault substitution hide the attacker-controlled asset behind a trusted-looking flow.",
    "order": 1,
    "stage": "vulnerabilities",
    "vulnerability_id": "7ca39d1b-f483-5853-b51b-b6875931d961",
    "vulnerability_category": "token_validation",
    "difficulty": "easy",
    "objectives": [
      "Identify the missing mint authenticity check.",
      "Prepare the deterministic devnet challenge state.",
      "Execute the wallet-signed exploit transaction.",
      "Submit the transaction signature for deterministic verification."
    ],
    "instructions": "Connect a wallet, start the level, run setup, sign the exploit transaction on devnet, and submit the resulting transaction signature. The backend prepares challenge metadata and verifies outcomes; it never signs or submits for you.",
    "verification_requirements": [
      "Transaction must exist and succeed on Solana devnet.",
      "Connected wallet must be a signer.",
      "Transaction must include the session-bound challenge accounts.",
      "Level session and wallet must match the setup context.",
      "Transaction signature must not have been used before."
    ],
    "repository_url": null,
    "resources": [
      {
        "label": "Starter repo",
        "url": "https://example.com/solbreach/level-1"
      }
    ],
    "verification_config": {
      "checks": [
        { "type": "session_binding" },
        { "type": "replay_protection" },
        { "type": "transaction_signature", "require_success": true },
        {
          "type": "solana_transaction",
          "require_success": true,
          "require_wallet_signer": true,
          "require_challenge_accounts": true
        }
      ]
    },
    "deployment_info": {
      "mode": "deterministic_proof",
      "execution": {
        "enabled": true,
        "mode": "wallet_signed_demo_transaction",
        "network": "devnet",
        "program_id": "11111111111111111111111111111111",
        "demo_mode": true
      }
    },
    "xp_reward": 100,
    "is_active": true,
    "created_at": "2026-05-21T14:35:00.000000Z",
    "updated_at": "2026-05-21T14:35:00.000000Z"
  },
  "state": "in_progress",
  "session": {
    "id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
    "user_id": "c290a1a5-045d-4adb-8ceb-a6c3f59d9e8b",
    "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
    "state": "in_progress",
    "attempt_count": 0,
    "started_at": "2026-05-21T14:35:00.000000Z",
    "completed_at": null,
    "last_submitted_at": null,
    "setup_at": null,
    "exploit_status": "not_started",
    "wallet_address": null,
    "challenge_context": {},
    "tx_signature": null,
    "verified_at": null
  },
  "execution": {
    "setup_required": true,
    "network": "devnet",
    "setup_endpoint": "/api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/setup",
    "submit_proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
    "execution_mode": "wallet_signed_demo_transaction"
  }
}
```

Possible errors:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing bearer token"
  }
}
```

```json
{
  "error": {
    "code": "LEVEL_LOCKED",
    "message": "Complete the previous level before starting this one"
  }
}
```

### Setup Challenge

```txt
POST /api/v1/levels/{level_id}/setup
```

Auth: required.

Request body:

```json
{
  "wallet_address": "DemoWallet111111111111111111111111111111111"
}
```

Success status: `200 OK`.

Example response:

```json
{
  "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
  "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
  "exploit_status": "setup_ready",
  "challenge": {
    "network": "devnet",
    "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
    "wallet_address": "DemoWallet111111111111111111111111111111111",
    "program_id": "11111111111111111111111111111111",
    "official_mint": "7aPAqFTyYx9pDumrJjVYddtdLyqXJZCWkaghrBfCojZq",
    "official_vault": "EA9GzZ4GCrLU6Wmh4AEfa1AZQywrfz6sfgYbzxksmj26",
    "fake_mint": "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
    "fake_vault": "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
    "challenge_pda": "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
    "attacker_token_account": "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n",
    "required_accounts": [
      "11111111111111111111111111111111",
      "7aPAqFTyYx9pDumrJjVYddtdLyqXJZCWkaghrBfCojZq",
      "EA9GzZ4GCrLU6Wmh4AEfa1AZQywrfz6sfgYbzxksmj26",
      "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
      "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
      "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
      "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n",
      "DemoWallet111111111111111111111111111111111"
    ],
    "required_pdas": [
      {
        "label": "challenge_pda",
        "address": "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
        "seeds": ["solbreach", "level-1-fake-mint", "fba5ffad-de30-4d6e-abda-0ffc84df23b7"]
      }
    ],
    "exploit_parameters": {
      "vulnerability": "fake_mint",
      "mode": "wallet_signed_demo_transaction",
      "demo_mode": true,
      "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
      "verification_focus": [
        "transaction_exists",
        "transaction_succeeded",
        "wallet_signed",
        "required_accounts_included",
        "session_binding",
        "replay_protection"
      ]
    }
  }
}
```

Setup is idempotent for the same active session and wallet. Calling setup again with the same wallet returns the same challenge.

Possible errors:

```json
{
  "error": {
    "code": "LEVEL_NOT_STARTED",
    "message": "Start the level before setup"
  }
}
```

```json
{
  "error": {
    "code": "LEVEL_SETUP_ALREADY_BOUND",
    "message": "Level session is already bound to another wallet"
  }
}
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "[{\"type\":\"string_too_short\",\"loc\":[\"body\",\"wallet_address\"],\"msg\":\"String should have at least 32 characters\"}]"
  }
}
```

### Get Level Status

```txt
GET /api/v1/levels/{level_id}/status
```

Auth: required.

Request body: none.

Success status: `200 OK`.

Example response after setup:

```json
{
  "level": {
    "id": "96d2111d-bb01-5a1b-9536-57331fed473e",
    "slug": "level-1-fake-mint",
    "title": "Level 1: The Illusionist",
    "order": 1,
    "stage": "vulnerabilities",
    "vulnerability_id": "7ca39d1b-f483-5853-b51b-b6875931d961",
    "vulnerability_category": "token_validation",
    "difficulty": "easy",
    "description": "Exploit a fake mint path where counterfeit token accounts and vault substitution hide the attacker-controlled asset behind a trusted-looking flow.",
    "objectives": [
      "Identify the missing mint authenticity check.",
      "Prepare the deterministic devnet challenge state.",
      "Execute the wallet-signed exploit transaction.",
      "Submit the transaction signature for deterministic verification."
    ],
    "instructions": "Connect a wallet, start the level, run setup, sign the exploit transaction on devnet, and submit the resulting transaction signature. The backend prepares challenge metadata and verifies outcomes; it never signs or submits for you.",
    "verification_requirements": [
      "Transaction must exist and succeed on Solana devnet.",
      "Connected wallet must be a signer.",
      "Transaction must include the session-bound challenge accounts.",
      "Level session and wallet must match the setup context.",
      "Transaction signature must not have been used before."
    ],
    "repository_url": null,
    "resources": [
      {
        "label": "Starter repo",
        "url": "https://example.com/solbreach/level-1"
      }
    ],
    "verification_config": {
      "checks": [
        { "type": "session_binding" },
        { "type": "replay_protection" },
        { "type": "transaction_signature", "require_success": true },
        {
          "type": "solana_transaction",
          "require_success": true,
          "require_wallet_signer": true,
          "require_challenge_accounts": true
        }
      ]
    },
    "deployment_info": {
      "mode": "deterministic_proof",
      "example_proof": {
        "transaction_signature": "demo-signature-level-1-abcdef",
        "transaction_succeeded": true
      },
      "demo_wallet": "DemoWallet111111111111111111111111111111111",
      "demo_accounts": {
        "fake_mint": "FakeMint11111111111111111111111111111111111",
        "vault": "Vault111111111111111111111111111111111111"
      },
      "execution": {
        "enabled": true,
        "mode": "wallet_signed_demo_transaction",
        "network": "devnet",
        "program_id": "11111111111111111111111111111111",
        "demo_mode": true
      }
    },
    "xp_reward": 100,
    "is_active": true,
    "created_at": "2026-05-21T14:35:00.000000Z",
    "updated_at": "2026-05-21T14:35:00.000000Z"
  },
  "state": "in_progress",
  "unlock_status": "unlocked",
  "available": true,
  "session": {
    "id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
    "user_id": "c290a1a5-045d-4adb-8ceb-a6c3f59d9e8b",
    "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
    "state": "in_progress",
    "attempt_count": 0,
    "started_at": "2026-05-21T14:35:00.000000Z",
    "completed_at": null,
    "last_submitted_at": null,
    "setup_at": "2026-05-21T14:36:00.000000Z",
    "exploit_status": "setup_ready",
    "wallet_address": "DemoWallet111111111111111111111111111111111",
    "challenge_context": {
      "network": "devnet",
      "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
      "wallet_address": "DemoWallet111111111111111111111111111111111",
      "fake_mint": "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
      "fake_vault": "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
      "challenge_pda": "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
      "attacker_token_account": "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n"
    },
    "tx_signature": null,
    "verified_at": null
  },
  "completed": false,
  "progress": null,
  "submissions": [],
  "xp_awarded": 0,
  "xp_earned": 0,
  "next_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
  "exploit_status": "setup_ready",
  "challenge_context": {
    "network": "devnet",
    "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
    "wallet_address": "DemoWallet111111111111111111111111111111111",
    "fake_mint": "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
    "fake_vault": "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
    "challenge_pda": "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
    "attacker_token_account": "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n"
  }
}
```

Frontend should treat `level.verification_config` and `level.deployment_info` as read-only metadata. Build transactions from `/setup.challenge`, not by reverse-engineering `verification_config`.

### Submit Proof

```txt
POST /api/v1/levels/{level_id}/submit
```

Auth: required.

Request body:

```json
{
  "transaction_signature": "5UBXMiJ4txXnK9BNXkhkXyGjVD8EG9UsQYo3Tf1SRQp6vCVs6F9rtD1V3QAH4L5i4hJ8yQpT9hEiS94UnnLv4B9M",
  "wallet_address": "DemoWallet111111111111111111111111111111111",
  "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7"
}
```

Success status: `200 OK`.

Successful verification response:

```json
{
  "success": true,
  "data": {
    "submission_status": "VERIFIED",
    "level_completed": true,
    "xp_awarded": 100,
    "next_level_unlocked": true,
    "unlocked_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
    "submission": {
      "id": "742c1786-0f20-4496-bc9b-7fd2c47c43da",
      "user_id": "c290a1a5-045d-4adb-8ceb-a6c3f59d9e8b",
      "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
      "session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
      "attempt_number": 1,
      "payload": {
        "transaction_signature": "5UBXMiJ4txXnK9BNXkhkXyGjVD8EG9UsQYo3Tf1SRQp6vCVs6F9rtD1V3QAH4L5i4hJ8yQpT9hEiS94UnnLv4B9M",
        "wallet_address": "DemoWallet111111111111111111111111111111111",
        "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
        "transaction_succeeded": true
      },
      "status": "verified",
      "verification_message": "Verification succeeded",
      "verification_result": {
        "verified": true,
        "message": "Verification succeeded",
        "checks": [
          {
            "name": "session_binding",
            "passed": true,
            "message": "Session binding accepted",
            "details": {}
          },
          {
            "name": "replay_protection",
            "passed": true,
            "message": "Transaction signature is unique",
            "details": {}
          },
          {
            "name": "transaction_signature",
            "passed": true,
            "message": "Transaction proof accepted",
            "details": {}
          },
          {
            "name": "solana_transaction",
            "passed": true,
            "message": "Solana transaction proof accepted",
            "details": {}
          },
        ]
      },
      "created_at": "2026-05-21T14:37:00.000000Z",
      "updated_at": "2026-05-21T14:37:00.000000Z"
    },
    "progress": {
      "id": "b43bf19f-021b-44e0-bc25-ea5cb597d1ad",
      "user_id": "c290a1a5-045d-4adb-8ceb-a6c3f59d9e8b",
      "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
      "xp_awarded": 100,
      "completed_at": "2026-05-21T14:37:00.000000Z"
    },
    "certification": null
  },
  "error": null
}
```

Failed verification response:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_SUBMISSION",
    "message": "Verification failed",
    "details": {
      "verified": false,
      "message": "Verification failed",
      "checks": [
        {
          "name": "solana_transaction",
          "passed": false,
          "message": "Transaction was not found on devnet",
          "details": {}
        }
      ]
    }
  }
}
```

Hard error response for reused transaction signature:

```json
{
  "error": {
    "code": "INVALID_SUBMISSION",
    "message": "Transaction signature was already submitted"
  }
}
```

## Transaction Construction Requirements

The backend does not return a serialized transaction. The frontend must build and submit a Solana devnet transaction using wallet adapter.

Required transaction properties:

- The connected wallet must sign the transaction.
- The submitted signature must resolve on `https://api.devnet.solana.com`.
- The transaction must succeed. In Solana RPC this means `meta.err` is `null`.
- The transaction must include every address from `challenge.required_accounts`.
- The transaction does not need to use SPL Token instructions for the demo.
- The deterministic challenge accounts may be included as read-only account keys.

Expected instructions:

- Backend does not inspect instruction data, discriminators, or program logs.
- Backend inspects the confirmed transaction account keys, success status, signer list, session binding, and replay status.
- Therefore the frontend exploit builder may use a simple wallet-signed demo transaction, such as a memo-style transaction, as long as it includes every required challenge account.
- Do not use SPL Token transfer instructions against the deterministic challenge accounts. They are metadata addresses for the demo flow, not initialized SPL token accounts.
- The connected wallet must be the fee payer or otherwise present as a signer in the transaction message.

Required accounts from setup:

```json
[
  "11111111111111111111111111111111",
  "7aPAqFTyYx9pDumrJjVYddtdLyqXJZCWkaghrBfCojZq",
  "EA9GzZ4GCrLU6Wmh4AEfa1AZQywrfz6sfgYbzxksmj26",
  "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
  "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
  "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
  "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n",
  "DemoWallet111111111111111111111111111111111"
]
```

Expected frontend transaction sequence:

1. Read `challenge` from `/setup`.
2. Build the Level 1 exploit transaction for devnet.
3. Include all `challenge.required_accounts` in the transaction account keys.
4. Make the connected wallet the fee payer and signer.
5. Submit the signed transaction to devnet.
6. Wait for confirmation.
7. Submit only the proof payload to the backend.

The backend validates the transaction from Solana RPC. The frontend must not submit handcrafted token deltas for the devnet flow.

## Verification Requirements

Backend verification checks:

- Session binding:
  - `level_session_id` must equal the active session id.
  - `wallet_address` must equal the wallet used in `/setup`.
- Replay protection:
  - `transaction_signature` must not have been submitted before by any user.
- Transaction signature:
  - signature must be a string of at least 16 characters.
  - transaction must be marked successful after RPC lookup.
- Solana transaction:
  - transaction must exist on devnet.
  - transaction must have `meta.err == null`.
  - setup wallet must be one of the transaction signers.
  - all required challenge accounts must appear in the transaction account keys.
  - deterministic challenge accounts may be included as read-only metadata accounts.

## Frontend State Machine

Recommended frontend states:

```txt
disconnected
wallet_connected
level_loading
level_available
level_started
setup_pending
setup_ready
tx_building
tx_pending_wallet_signature
tx_submitting
tx_confirmed
verification_pending
verified
failed
```

State transitions:

```txt
disconnected -> wallet_connected
wallet_connected -> level_loading
level_loading -> level_available
level_available -> level_started
level_started -> setup_pending
setup_pending -> setup_ready
setup_ready -> tx_building
tx_building -> tx_pending_wallet_signature
tx_pending_wallet_signature -> tx_submitting
tx_submitting -> tx_confirmed
tx_confirmed -> verification_pending
verification_pending -> verified
verification_pending -> failed
```

Status mapping:

```txt
GET /status state=available      -> level_available
GET /status state=in_progress    -> level_started or setup_ready
GET /status exploit_status=setup_ready -> setup_ready
GET /status state=completed      -> verified
GET /status state=failed         -> failed
```

## Error Responses and Frontend Behavior

| Code | HTTP | Meaning | Frontend behavior |
| --- | --- | --- | --- |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT | Send user to login |
| `LEVEL_LOCKED` | 403 | User has not completed previous level | Show locked state |
| `LEVEL_NOT_STARTED` | 409 | Setup or submit called before start | Call `/start`, then retry |
| `LEVEL_SETUP_REQUIRED` | 409 | Submit called before setup | Call `/setup`, then retry |
| `LEVEL_SETUP_ALREADY_BOUND` | 409 | Active session is bound to a different wallet | Ask user to reconnect original wallet |
| `INVALID_SUBMISSION` | 403 or 200 with `success=false` | Verification failed or replay detected | Show failure details |
| `VALIDATION_ERROR` | 422 | Malformed payload | Fix client payload |
| `HTTP_ERROR` | varies | Generic FastAPI/HTTP error | Show generic retry/error state |

Common verification failures:

- Transaction not found on devnet.
- Transaction failed on devnet.
- Wallet did not sign the transaction.
- Transaction omitted required challenge accounts.
- Token balances did not match expected movement.
- Transaction signature was already submitted.
- Payload wallet did not match setup wallet.
- Payload session id did not match active session.

## Minimal Frontend Pseudocode

```ts
const start = await api.post(`/api/v1/levels/${levelId}/start`);

const setup = await api.post(`/api/v1/levels/${levelId}/setup`, {
  wallet_address: publicKey.toBase58(),
});

const challenge = setup.challenge;

const tx = await buildLevel1ExploitTransaction({
  wallet: publicKey,
  challenge,
  connection,
});

const signature = await sendTransaction(tx, connection);
await connection.confirmTransaction(signature, "confirmed");

const result = await api.post(`/api/v1/levels/${levelId}/submit`, {
  transaction_signature: signature,
  wallet_address: publicKey.toBase58(),
  level_session_id: setup.level_session_id,
});

if (result.success) {
  // show XP, mark completed, unlock Level 2
} else {
  // show result.error.details.checks
}
```
