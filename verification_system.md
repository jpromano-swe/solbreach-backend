
# SolBreach Verification System

# Objective

This document defines how exploit verification works in SolBreach.

Verification is the CORE mechanic of the platform.

The backend must validate:
- exploit success
- deterministic outcomes
- user progression

WITHOUT executing arbitrary user code.

---

# Verification Philosophy

SolBreach uses:
# deterministic proof validation

NOT:
- arbitrary code execution
- remote exploit execution
- sandboxed runtime validation (yet)

Users execute exploits independently.

The backend validates:
- resulting blockchain state
- expected artifacts
- expected outcomes

---

# Initial Verification Methods

## 1. Transaction Signature Validation

User submits:
- transaction signature

Backend verifies:
- transaction exists
- transaction succeeded
- expected accounts modified

---

## 2. PDA State Validation

Backend validates:
- PDA ownership
- stored fields
- expected values

Example:
- completed_levels[0] == true

---

## 3. Token Balance Validation

Backend validates:
- expected token movement
- vault state
- exploit outcomes

---

## 4. Authority Validation

Backend checks:
- account authority changes
- spoofed authority success
- ownership transitions

---

# Verification Flow

## Step 1
User submits proof payload.

Example:

```json
{
  "transaction_signature": "...",
  "player_wallet": "...",
  "level_id": "..."
}