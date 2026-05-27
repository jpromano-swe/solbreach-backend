# SolBreach Demo Walkthrough: Level 1

This is the deterministic incubator demo sequence for Level 1, "The Illusionist".

Backend URL:

```txt
http://56.125.190.174:8000
```

Level 1 id:

```txt
96d2111d-bb01-5a1b-9536-57331fed473e
```

Level 2 id:

```txt
8bb6a9be-cc76-57ed-910f-99c73321cd36
```

## Demo Sequence

### 1. Register Or Login

Frontend state: `disconnected` or `wallet_connected`.

Request:

```txt
POST /api/v1/auth/register
```

Body:

```json
{
  "username": "demo_player",
  "email": "demo-player@example.com",
  "password": "strong-password"
}
```

Then:

```txt
POST /api/v1/auth/login
```

Body:

```json
{
  "email": "demo-player@example.com",
  "password": "strong-password"
}
```

Expected frontend transition:

```txt
unauthenticated -> authenticated
```

### 2. Connect Wallet

Frontend action: connect wallet adapter on Solana devnet.

Example wallet:

```txt
DemoWallet111111111111111111111111111111111
```

Expected frontend transition:

```txt
authenticated -> wallet_connected
```

### 3. Load Level 1

Request:

```txt
GET /api/v1/levels
```

Expected Level 1 catalog item:

```json
{
  "id": "96d2111d-bb01-5a1b-9536-57331fed473e",
  "slug": "level-1-fake-mint",
  "title": "Level 1: The Illusionist",
  "vulnerability_category": "token_validation",
  "difficulty": "easy",
  "xp_reward": 100
}
```

Expected frontend transition:

```txt
wallet_connected -> level_available
```

### 4. Start Level 1

Request:

```txt
POST /api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/start
```

Body: none.

Expected response fields:

```json
{
  "state": "in_progress",
  "session": {
    "id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
    "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
    "state": "in_progress",
    "attempt_count": 0,
    "exploit_status": "not_started"
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

Expected frontend transition:

```txt
level_available -> level_started
```

### 5. Setup Challenge

Request:

```txt
POST /api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/setup
```

Body:

```json
{
  "wallet_address": "DemoWallet111111111111111111111111111111111"
}
```

Expected response:

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

Expected frontend transition:

```txt
level_started -> setup_ready
```

### 6. Execute Exploit Transaction

Frontend action:

1. Build Level 1 exploit transaction for devnet.
2. Include every `challenge.required_accounts` address in the transaction account keys.
3. Set connected wallet as fee payer and signer.
4. Submit transaction to Solana devnet.
5. Wait for confirmation.

Expected transaction outcome:

```json
{
  "meta.err": null,
  "wallet_is_signer": true,
  "required_accounts_included": true
}
```

For the demo, do not execute SPL Token instructions against the deterministic challenge accounts. They are not initialized SPL token accounts. A simple wallet-signed transaction that includes the required accounts is enough for Level 1 verification.

Expected frontend transition:

```txt
setup_ready -> tx_pending_wallet_signature -> tx_submitting -> tx_confirmed
```

### 7. Submit Proof

Request:

```txt
POST /api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/submit
```

Body:

```json
{
  "transaction_signature": "5UBXMiJ4txXnK9BNXkhkXyGjVD8EG9UsQYo3Tf1SRQp6vCVs6F9rtD1V3QAH4L5i4hJ8yQpT9hEiS94UnnLv4B9M",
  "wallet_address": "DemoWallet111111111111111111111111111111111",
  "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7"
}
```

Expected success response:

```json
{
  "success": true,
  "data": {
    "submission_status": "VERIFIED",
    "level_completed": true,
    "xp_awarded": 100,
    "next_level_unlocked": true,
    "unlocked_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36"
  },
  "error": null
}
```

Expected frontend transition:

```txt
tx_confirmed -> verification_pending -> verified
```

### 8. Confirm Progression

Request:

```txt
GET /api/v1/levels/96d2111d-bb01-5a1b-9536-57331fed473e/status
```

Expected response fields:

```json
{
  "state": "completed",
  "completed": true,
  "xp_awarded": 100,
  "xp_earned": 100,
  "exploit_status": "verified",
  "next_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36"
}
```

Request:

```txt
GET /api/v1/levels/8bb6a9be-cc76-57ed-910f-99c73321cd36/status
```

Expected response fields:

```json
{
  "state": "available",
  "unlock_status": "unlocked",
  "available": true
}
```

Expected frontend transition:

```txt
verified -> level_2_unlocked
```

## Demo Failure Recovery

If proof submission returns:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_SUBMISSION",
    "message": "Verification failed"
  }
}
```

Frontend should:

1. Keep the user on Level 1.
2. Show the failed verification checks from `error.details.checks`.
3. Allow retry with a new transaction signature.

If proof submission returns:

```json
{
  "error": {
    "code": "INVALID_SUBMISSION",
    "message": "Transaction signature was already submitted"
  }
}
```

Frontend should:

1. Explain that the transaction was already used.
2. Require a fresh exploit transaction.

If setup returns `LEVEL_SETUP_ALREADY_BOUND`, frontend should ask the user to reconnect the wallet originally used for setup.
