# SolBreach Frontend Integration: Level 3

This document is the frontend contract for Level 3, "The Trojan Horse".

## API Base

Use the production backend base URL:

```txt
https://api-solbreach.56.125.190.174.nip.io
```

## Gameplay Flow

1. User completes Levels 1 and 2.
2. Frontend runs Observe locally. No backend call is required.
3. Frontend runs Manipulate locally. No backend call is required.
4. Frontend enters Inspect and calls Level 3 setup.
5. Backend returns deterministic delegated-CPI challenge accounts.
6. Frontend builds and submits a wallet-signed devnet transaction containing every required account.
7. Frontend submits the transaction signature to the backend.
8. Backend verifies the transaction, awards XP, unlocks Level 4, and returns a certification object with `mint_status: "not_minted"`.

## Endpoints

### Start

```http
POST /api/v1/levels/{level_3_id}/start
Authorization: Bearer <jwt>
```

Successful response:

```json
{
  "state": "in_progress",
  "execution": {
    "setup_required": true,
    "network": "devnet",
    "setup_endpoint": "/api/v1/levels/e77c8525-c328-517b-b95f-4551c70a8834/setup",
    "submit_proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
    "execution_mode": "wallet_signed_demo_transaction"
  }
}
```

### Setup

```http
POST /api/v1/levels/{level_3_id}/setup
Authorization: Bearer <jwt>
Content-Type: application/json
```

Request:

```json
{
  "wallet_address": "PLAYER_WALLET"
}
```

Successful response shape:

```json
{
  "level_id": "LEVEL_3_UUID",
  "level_session_id": "uuid",
  "exploit_status": "setup_ready",
  "challenge": {
    "network": "devnet",
    "level_session_id": "uuid",
    "wallet_address": "PLAYER_WALLET",
    "program_id": "11111111111111111111111111111111",
    "guild_authority_pda": "...",
    "level3_state_pda": "...",
    "bounty_vault_pda": "...",
    "trusted_cpi_program": "...",
    "attacker_cpi_program": "...",
    "player_reward_account": "...",
    "authority_record_pda": "...",
    "required_accounts": [
      "PLAYER_WALLET",
      "guild_authority_pda",
      "level3_state_pda",
      "bounty_vault_pda",
      "trusted_cpi_program",
      "attacker_cpi_program",
      "player_reward_account",
      "authority_record_pda"
    ],
    "exploit_parameters": {
      "vulnerability": "arbitrary_cpi_delegated_signer_abuse",
      "mode": "wallet_signed_demo_transaction",
      "demo_mode": true,
      "attack_goal": "route delegated signer authority into attacker-controlled CPI and drain bounty credit to player reward account",
      "expected_sequence": ["target", "signer", "vault", "reward"],
      "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
      "verification_focus": [
        "transaction_exists",
        "transaction_succeeded",
        "wallet_signed",
        "required_accounts_included",
        "delegated_cpi_account_set",
        "expected_sequence",
        "session_binding",
        "replay_protection"
      ]
    }
  }
}
```

### Status

```http
GET /api/v1/levels/{level_3_id}/status
Authorization: Bearer <jwt>
```

The response includes the current state, submission history, XP earned, and any `challenge_context` created by setup.

### Submit

```http
POST /api/v1/levels/{level_3_id}/submit
Authorization: Bearer <jwt>
Content-Type: application/json
```

Request:

```json
{
  "transaction_signature": "tx_sig",
  "wallet_address": "PLAYER_WALLET",
  "level_session_id": "uuid"
}
```

Successful response:

```json
{
  "success": true,
  "data": {
    "submission_status": "VERIFIED",
    "level_completed": true,
    "xp_awarded": 300,
    "next_level_unlocked": true,
    "unlocked_level_id": "LEVEL_4_UUID",
    "certification": {
      "slug": "arbitrary-cpi-delegated-signer-abuse",
      "title": "Arbitrary CPI Delegated Signer Abuse",
      "unlock_status": "unlocked",
      "mint_status": "not_minted",
      "metadata": {
        "completed_level_order": 3,
        "stage": "vulnerabilities",
        "minting_enabled": true
      }
    }
  },
  "error": null
}
```

## Transaction Requirements

The frontend must build a successful Solana devnet transaction with:

- connected wallet as the only signer
- all deterministic challenge accounts marked `isSigner: false`
- every `challenge.required_accounts` address included in account metas
- successful confirmation where `meta.err == null`
- no SPL token instructions
- no real CPI execution requirement for the demo

Memo or a lightweight SystemProgram transaction is acceptable if it includes the required account metas.

## Backend Verification

Backend verifies:

- transaction exists on devnet
- transaction succeeded
- submitted wallet signed
- every `challenge.required_accounts` address appears in transaction account keys
- delegated-CPI challenge account labels are present
- `expected_sequence` is `["target", "signer", "vault", "reward"]`
- `level_session_id` matches the active setup session
- `wallet_address` matches setup
- transaction signature has not been reused

Backend does not:

- sign transactions
- hold private keys
- execute arbitrary code
- execute a real CPI exploit
- require initialized SPL token accounts
- mint certification NFTs on-chain yet

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
- missing delegated-CPI challenge accounts
- wrong `level_session_id`
- wallet mismatch against setup
- reused transaction signature
