# SolBreach Backend Handoff — RL1 Account Substitution Research Lab

## Context

SolBreach is currently focused on shipping **Research Lab 1 (RL1)** as the canonical Research Lab template.

RL1 is **not** a patch-the-code challenge. It is a security-auditor workflow where the learner:

1. Inspects vulnerable protocol code and account context.
2. Submits controlled sandbox actions.
3. Reviews transaction/account/log evidence.
4. Runs backend impact verification.
5. Completes a deterministic Finding Review questionnaire.
6. Builds a deterministic Audit Report.
7. Unlocks the certificate only after backend-confirmed completion.

The vulnerability family for RL1 is:

```text
Account Substitution / Missing Account Binding
```

The concrete lab scenario is a vault/lending-style flow where a caller can submit non-canonical collateral/vault account relationships, receive illegitimate credit, then withdraw/borrow real protocol value.

## Product Principle To Preserve

Do not let the frontend decide completion.

The backend must be the source of truth for:

- `impactVerified`
- `findingReviewPassed`
- `auditReportBuilderPassed`
- `verifiedEvidenceRefs`
- `certificateUnlockable`

The frontend may display state, but it must not infer certificate/report unlocks from local UI state, successful transaction status, or draft report existence.

## Current Frontend Risk

The frontend currently derives `impactVerified` too broadly from fields such as:

- `session.labCompleted`
- `session.status === "passed"`
- `session.reportStatus`
- `report.status === "draft" | "retry" | "accepted"`

This is risky unless those values are guaranteed to mean backend-verified exploit impact.

Please expose explicit backend fields so the frontend does not infer:

- `impactVerified: boolean`
- `verifiedEvidenceRefs: string[]`
- `reportUnlocked: boolean`
- `certificateUnlockable: boolean`

## Required RL1 Backend Flow

### 1. Session Creation

When a learner opens RL1, create an isolated backend/SVM-backed session.

The session should include:

- `sessionId: string`
- `labId: "rl1-account-substitution"`
- `status: "active" | "running" | "verified" | "completed" | "failed" | "expired"`
- `phase: "INSPECT" | "EXECUTE_EXPLOIT" | "EVIDENCE_REVIEW" | "SUBMIT_FINDING" | "COMPLETED"`
- `impactVerified: boolean`
- `verifiedEvidenceRefs: string[]`
- `reportStatus: "locked" | "draft" | "retry" | "accepted"`
- `certificateUnlockable: boolean`

Avoid legacy fix stages for RL1. This lab is not about patching code.

### 2. Controlled Transaction Endpoint

The frontend submits controlled actions, not arbitrary exploit scripts.

Expected action payloads:

```ts
type LabTransactionPayload =
  | {
      action_type: "DEPOSIT_COLLATERAL";
      amount: number;
      collateral_account_ref: string;
      vault_account_ref: string;
    }
  | {
      action_type: "WITHDRAW_AGAINST_CREDIT";
      amount: number;
    };
```

Backend requirements:

- Execute the requested action inside the session’s sandbox/SVM state.
- Record transaction result, logs, account refs, pre/post state.
- Do not auto-run missing exploit steps.
- Do not mark impact verified just because a transaction succeeds.
- Return observational wording only.

Response shape should include:

```json
{
  "transactionRef": "string",
  "instructionType": "string",
  "executionStatus": "success",
  "logs": ["string"],
  "accountDeltas": [],
  "evidenceRefs": ["string"]
}
```

### 3. Verify Impact Endpoint

`POST /research-labs/sessions/:sessionId/verify-objective`

This endpoint must only inspect existing session state. It must not execute missing actions.

It should verify all required conditions:

- `counterfeitDepositObserved === true`
- `unapprovedCollateralSourceUsed === true`
- `nonCanonicalVaultDestinationUsed === true`
- `positionCreditIncreasedFromInvalidRelationship === true`
- `withdrawOrBorrowAgainstInvalidCreditObserved === true`
- `realProtocolTreasuryValueDecreased === true`

A successful deposit alone is not enough.

A successful withdrawal alone is not enough.

Impact is proven only when illegitimate credit from an unapproved account relationship is used to withdraw/borrow real protocol value.

Recommended response:

```json
{
  "sessionId": "string",
  "passed": true,
  "impactVerified": true,
  "reportUnlocked": true,
  "phase": "SUBMIT_FINDING",
  "verifiedEvidenceRefs": ["string"],
  "evidence": {
    "transactionTimeline": [],
    "accountDeltas": [],
    "runtimeLogs": [],
    "impactChecklist": {
      "counterfeitDepositObserved": true,
      "invalidCreditAssigned": true,
      "treasuryValueMoved": true,
      "exploitProvenanceConfirmed": true
    }
  },
  "failureReason": null
}
```

## Audit Report Backend Requirements

The Audit Report must be deterministic for v1.

Do not validate arbitrary free text for certificate unlock.

The frontend should submit selected option IDs, not prose-only fields.

Suggested backend report fields:

```ts
type AuditReportSubmission = {
  titleOptionId: string;
  severityOptionId: string;
  likelihoodOptionId: string;
  categoryOptionId: string;
  rootCauseOptionId: string;
  proofOfImpactOptionId: string;
  recommendedMitigationOptionId: string;
  verifiedEvidenceRefs: string[];
  optionalNotes?: string;
};
```

Backend should validate accepted IDs for RL1:

- `titleOptionId === "missing_constraints_counterfeit_credit"`
- `severityOptionId === "high_treasury_loss"`
- `likelihoodOptionId === "medium_high_attacker_supplied_accounts"`
- `categoryOptionId === "account_substitution"`
- `rootCauseOptionId === "missing_account_binding"`
- `proofOfImpactOptionId === "counterfeit_credit_withdraws_treasury"`
- `recommendedMitigationOptionId === "bind_accounts_to_approved_config"`
- `verifiedEvidenceRefs.length > 0`
- `impactVerified === true`
- `findingReviewPassed === true`

Optional notes may be saved, but must not affect deterministic pass/fail.

## Finding Review

The questionnaire can be frontend-rendered, but backend should either:

- Grade it deterministically, or
- Receive the deterministic result and persist it only if the submitted answers match expected IDs.

Preferred backend-owned state:

- `findingReviewPassed: boolean`
- `findingReviewAttempts: number`
- `failedQuestionIds: string[]`
- `criticalQuestionsPassed: boolean`

Critical questions must be correct:

- `q1_vulnerability_category`
- `q4_exploit_sequence`
- `q6_impact_proven`
- `q8_recommended_fix`

Passing condition:

```text
score >= 80 && failedCriticalQuestions.length === 0
```

## Certificate Unlock Rule

The backend must only unlock the RL1 certificate when all are true:

- `impactVerified === true`
- `findingReviewPassed === true`
- `auditReportBuilderPassed === true`
- `verifiedEvidenceRefs.length > 0`

Recommended certificate name:

```text
Account Substitution — Verified Research Lab
```

Do not let a draft report, successful transaction, or frontend navigation state unlock the certificate.

## Legacy/Stale Concepts To Remove

RL1 should not use:

- Vault Mirage
- arithmetic safety
- vault health calculation
- checked arithmetic patching
- oracle manipulation
- fix stage
- patch-the-code tasks

Those are stale concepts from an older lab direction and conflict with RL1.

## Backend Acceptance Criteria

- Verify Impact reads existing SVM/session state and never executes missing exploit steps.
- Successful transaction status alone never marks impact verified.
- Backend returns explicit `impactVerified`, `verifiedEvidenceRefs`, `reportUnlocked`, and `certificateUnlockable`.
- Report submission validates deterministic option IDs.
- Certificate unlock requires verified impact, passed review, accepted report fields, and evidence refs.
- RL1 copy/data/contracts refer to Account Substitution, not arithmetic/Vault Mirage.
- Tests cover happy path and failure paths:
  - regular deposit only: not verified
  - counterfeit deposit only: not verified
  - withdrawal without invalid credit: not verified
  - counterfeit deposit plus treasury withdrawal: verified
  - report submitted with wrong option IDs: rejected
  - report submitted without evidence refs: rejected
  - certificate request before full completion: rejected
