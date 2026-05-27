# SolBreach Frontend Integration: Level 2

This document is the frontend contract for Level 2, "Static PDA Commander".

## API Base

Use the same backend base URL as Level 1.

```txt
https://api-solbreach.56.125.190.174.nip.io
```

## Gameplay Flow

1. User completes Level 1.
2. Frontend loads Level 2 status.
3. Frontend starts Level 2.
4. Frontend calls setup with the connected wallet.
5. Frontend builds a wallet-signed devnet transaction that includes every required account.
6. Frontend submits the transaction to Solana devnet.
7. Frontend submits the transaction signature to the backend.
8. Backend verifies the transaction, awards XP, unlocks Level 3, and returns a certification object with `mint_status: "not_minted"`.

## Endpoints

### Start

```http
POST /api/v1/levels/{level_id}/start
Authorization: Bearer <jwt>
```

Successful response:

```json
{
  "state": "in_progress",
  "execution": {
    "setup_required": true,
    "network": "devnet",
    "setup_endpoint": "/api/v1/levels/8bb6a9be-cc76-57ed-910f-99c73321cd36/setup",
    "submit_proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
    "execution_mode": "wallet_signed_demo_transaction"
  }
}
```

### Setup

```http
POST /api/v1/levels/{level_id}/setup
Authorization: Bearer <jwt>
Content-Type: application/json
```

Request:

```json
{
  "wallet_address": "CommanderWallet11111111111111111111111111"
}
```

Successful response shape:

```json
{
  "level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
  "level_session_id": "adf7c0f1-7f58-4956-b6cb-9bb4f8d8c9b0",
  "exploit_status": "setup_ready",
  "challenge": {
    "network": "devnet",
    "level_session_id": "adf7c0f1-7f58-4956-b6cb-9bb4f8d8c9b0",
    "wallet_address": "CommanderWallet11111111111111111111111111",
    "program_id": "11111111111111111111111111111111",
    "commander_registry_pda": "8J7n...",
    "trusted_commander_pda": "9tm...",
    "hijacked_commander_pda": "6sQ...",
    "authority_record_pda": "G6b...",
    "static_seed_pda": "Bpo...",
    "expected_commander_after_hijack": "CommanderWallet11111111111111111111111111",
    "required_accounts": [
      "11111111111111111111111111111111",
      "8J7n...",
      "9tm...",
      "6sQ...",
      "G6b...",
      "Bpo...",
      "CommanderWallet11111111111111111111111111"
    ],
    "exploit_parameters": {
      "vulnerability": "static_pda_commander_hijack",
      "mode": "wallet_signed_demo_transaction",
      "demo_mode": true,
      "attack_goal": "replace the trusted commander PDA path with the wallet-bound commander",
      "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
      "verification_focus": [
        "transaction_exists",
        "transaction_succeeded",
        "wallet_signed",
        "required_accounts_included",
        "pda_commander_hijack_accounts",
        "session_binding",
        "replay_protection"
      ]
    }
  }
}
```

### Submit

```http
POST /api/v1/levels/{level_id}/submit
Authorization: Bearer <jwt>
Content-Type: application/json
```

Request:

```json
{
  "transaction_signature": "5UBXMiJ4txXnK9BNXkhkXyGjVD8EG9UsQYo3Tf1SRQp6vCVs6F9rtD1V3QAH4L5i4hJ8yQpT9hEiS94UnnLv4B9M",
  "wallet_address": "CommanderWallet11111111111111111111111111",
  "level_session_id": "adf7c0f1-7f58-4956-b6cb-9bb4f8d8c9b0"
}
```

Successful response:

```json
{
  "success": true,
  "data": {
    "submission_status": "VERIFIED",
    "level_completed": true,
    "xp_awarded": 250,
    "next_level_unlocked": true,
    "unlocked_level_id": "e77c8525-c328-517b-b95f-4551c70a8834",
    "certification": {
      "slug": "static-pda-commander-hijack",
      "title": "Static PDA Commander Hijack",
      "unlock_status": "unlocked",
      "mint_status": "not_minted",
      "metadata": {
        "completed_level_order": 2,
        "stage": "vulnerabilities",
        "minting_enabled": true
      }
    }
  },
  "error": null
}
```

## Transaction Requirements

The backend does not return a serialized transaction and does not sign anything.

The frontend must build a Solana devnet transaction with:

- connected wallet as signer
- successful confirmation where `meta.err == null`
- every `challenge.required_accounts` address included in the transaction account keys
- no SPL Token account requirement
- no backend-generated private key or server-side signature

For the demo, the required PDA addresses are deterministic metadata accounts. The transaction may include them as read-only account keys.

## Failure Cases

Expected backend failure response:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_SUBMISSION",
    "message": "Verification failed",
    "details": {
      "verified": false,
      "message": "Verification failed"
    }
  }
}
```

Common failure reasons:

- transaction not found on devnet
- transaction failed
- connected wallet did not sign
- missing commander challenge accounts
- wrong `level_session_id`
- wallet mismatch against setup
- reused transaction signature
