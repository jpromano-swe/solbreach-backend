# RL1 Backend Contract

## Scope

This document is the backend source of truth for Research Lab 1:

- canonical lab id: `rl1-account-substitution`
- learner slug: `account-substitution`
- objective ref: `RL1_ACCOUNT_SUBSTITUTION_IMPACT`

RL1 is a deterministic LiteSVM-backed exploit lab. Frontend and QA should treat the API contract here as canonical.

## Runtime semantics

RL1 models protocol semantics, not arbitrary free-form sandbox execution.

Initial state:

- official collateral account starts with `50,000`
- counterfeit collateral account starts with `500,000`
- treasury starts with `5,000,000,000` lamports
- reward wallet starts with `1,000,000,000` lamports
- LTV is `8,000` bps

Deposit paths:

- official path:
  - `official_collateral_account` -> `official_vault_account`
  - creates legitimate credit
- exploit path:
  - `attacker_collateral_account` -> `counterfeit_vault_account`
  - creates invalid credit
- mixed path:
  - both official and exploit deposits occurred in the same session

Borrow semantics:

- borrowability is computed from protocol credit state
- RL1 verification requires the exploit path to drain the backend-computed max borrow amount
- partial exploit borrow must fail verification

## Naming and template aliasing

Learner-facing RL1 identity is canonical:

- template ref exposed by the manifest: `research-labs/account-substitution@v1`
- entry file exposed by the manifest: `programs/account_substitution/src/lib.rs`

The backing runtime asset is still stored under the historical internal name:

- `research-labs/treasury-mirage@v1`
- `treasury_mirage.so`

This is intentional. Runtime resolvers map the canonical RL1 alias to the internal template path so existing deterministic session/account derivation remains stable while frontend/product naming stays aligned.

## Session contract

`GET /api/v1/research-labs/sessions/{session_id}` and `POST /api/v1/research-labs/{lab_id}/sessions` must expose:

- `labId`
- `impactVerified`
- `reportUnlocked`
- `reportStatus`
- `verifiedEvidenceRefs`
- `protocolState`

`protocolState` is the current learner-visible protocol snapshot. At minimum it contains:

- `depositPathType`
- `creditedCollateral`
- `maxBorrow`
- `availableBorrow`
- `borrowedTotal`
- `borrowAllowed`
- `ltvBps`
- `maxDrainSatisfied`

## Transaction contract

`POST /api/v1/research-labs/sessions/{session_id}/transactions`

The response must expose:

- `accountDeltas`
- `evidenceRefs`
- `protocolState`
- `exploitProvenance`
- `creditedCollateral`
- `maxBorrow`
- `availableBorrow`
- `borrowedTotal`
- `treasuryImpactObserved`
- `userFacingEvidence`

The transaction history endpoint must return the persisted transaction payload, not a recomputed partial view.

## Verification contract

`POST /api/v1/research-labs/sessions/{session_id}/verify-objective`

Happy path requirements:

1. successful exploit deposit observed
2. non-canonical vault destination observed
3. invalid credit created
4. treasury value decreased
5. exploit provenance confirmed
6. no mixed official/exploit provenance
7. max-drain semantics satisfied

Wrong paths must fail with explicit reasons:

- official path only
- partial exploit borrow
- mixed provenance
- no invalid deposit
- no treasury movement

Verification response must expose:

- `passed`
- `impactVerified`
- `verifiedEvidenceRefs`
- `reportUnlocked`
- `failureReason`
- `userFacingEvidence`
- `evidence.protocolState`
- `evidence.impactChecklist`

## Report contract

Report remains locked until `impactVerified == true`.

Endpoints:

- `GET /api/v1/research-labs/sessions/{session_id}/report`
- `PUT /api/v1/research-labs/sessions/{session_id}/report`
- `POST /api/v1/research-labs/sessions/{session_id}/report/submit`

Rules:

- `GET /report` must always return normalized persisted fields after unlock, save, retry, and acceptance
- `PUT /report` must persist option ids and `verifiedEvidenceRefs`
- `POST /report/submit` must reject empty or mismatched fields
- accepted responses must return stored fields, not only status

Report payload fields:

- `session_id`
- `sessionId`
- `status`
- `impactVerified`
- `reportUnlocked`
- `fields`
- `feedback`
- `verifiedEvidenceRefs`
- `certificateUnlockable`
- `allowed_values`
- `allowedValues`

## Finding review contract

Finding review payload must expose:

- `findingReviewPassed`
- `findingReviewAttempts`
- `failedQuestionIds`
- `criticalQuestionsPassed`
- `reportUnlocked`
- `certificateUnlockable`

## Deployment identity and observability

Health and version endpoints:

- `GET /health`
- `GET /version`

Both must expose:

- `stage`
- `environment`
- `deploy_version`
- `deploy_commit_sha`

Response headers:

- `X-SolBreach-Stage`
- `X-SolBreach-Deploy-Version`
- `X-SolBreach-Deploy-Commit-Sha`

Lambda cold start must log:

- stage
- environment
- deploy version
- deploy commit sha

## Backend-testing mapping

Current non-production environment:

- Lambda function: `solbreach-backend-backend-testing-api`
- region: `sa-east-1`
- API stage: `backend-testing`

## AWS debugging path

Use this sequence when RL1 behavior looks stale or inconsistent:

1. call `/health` and `/version`
2. confirm response headers include deploy version and commit sha
3. check Lambda `LastModified`
4. inspect CloudWatch logs for:
   - `solbreach_lambda_coldstart`
   - RL1 verification rejection/acceptance logs
   - RL1 report save/reject/accept logs
   - LiteSVM program load logs
5. rerun RL1 happy path and one negative path

## Golden path

1. create RL1 session
2. exploit deposit:
   - `attacker_collateral_account`
   - `counterfeit_vault_account`
3. borrow backend-computed max
4. verify objective
5. pass finding review
6. save report
7. submit accepted report
8. lab completes and XP is awarded
