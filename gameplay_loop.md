
# SolBreach Gameplay Loop

# Objective

This document defines the core gameplay lifecycle for SolBreach.

The goal is to create:
- deterministic progression
- adversarial learning
- realistic exploit workflows
- clear user feedback
- scalable progression systems

This is NOT a generic e-learning flow.

SolBreach is designed as:
# adversarial security training infrastructure.

---

# Core Gameplay Philosophy

Users should:
1. Understand a vulnerability
2. Reproduce an exploit
3. Verify exploitation success
4. Unlock progression
5. Build reputation

The platform should progressively transition users from:
- guided exploit solving
to:
- independent adversarial research.

---

# Current Platform Stages

## 1. Vulnerabilities
Structured exploit-focused levels.

Goal:
- learn exploit primitives
- understand attack vectors
- gain confidence

Examples:
- fake mint exploits
- unchecked CPI
- PDA misuse
- authority spoofing

---

## 2. Research Labs (Future)
Guided research environments.

Goal:
- investigate protocols
- interact with realistic repositories
- reproduce canonical exploits
- learn workflow familiarity

---

## 3. Breach Rooms (Future)
Advanced adversarial environments.

Goal:
- independent vulnerability discovery
- larger codebases
- ambiguity
- realistic audit simulations

---

# Current MVP Scope

The backend currently focuses ONLY on:
# Vulnerability Levels (Levels 0–3)

Research Labs and Breach Rooms are future extensions.

---

# User Gameplay Lifecycle

# 1. User Registration

User creates account.

Initial state:
- XP = 0
- no completed levels
- Level 0 unlocked
- certifications locked

---

# 2. User Starts Level

User selects a level.

Backend creates:
- level session
- attempt tracking
- start timestamp

Example endpoint:

POST /api/v1/levels/{level_id}/start

Response:
- level metadata
- instructions
- repository references
- downloadable resources
- verification requirements

---

# 3. User Solves Exploit Locally

The exploit happens:
- locally
- on devnet
- or inside future sandbox environments

The backend does NOT execute exploits.

The user performs the exploit independently.

---

# 4. User Submits Verification

User submits proof of exploit success.

Example:
POST /api/v1/levels/{level_id}/submit

Submission examples:
- transaction signature
- PDA address
- account state
- exploit artifact
- proof payload

---

# 5. Backend Verifies Exploit

Backend performs deterministic validation.

Validation examples:
- expected PDA ownership
- token balances
- account authority
- transaction existence
- expected program state

If valid:
- level marked complete
- XP awarded
- next level unlocked
- certification eligibility updated

---

# 6. Progression Update

System updates:
- XP
- completed levels
- unlocked content
- certifications

---

# 7. Certification Unlock

When a level group is completed:
- certification becomes unlockable

Initial implementation:
- database state only

Future:
- onchain cNFT minting

---

# Level States

Possible level states:

- LOCKED
- AVAILABLE
- IN_PROGRESS
- COMPLETED
- FAILED

---

# Submission States

Possible submission states:

- PENDING
- VERIFIED
- REJECTED

---

# MVP Gameplay Priorities

Priority order:
1. deterministic verification
2. reliable progression
3. clean UX
4. modular extensibility

NOT:
- blockchain minting
- real-time orchestration
- sandboxing
- advanced gamification

---

# Important Product Rules

## Backend Does NOT:
- execute exploits
- run arbitrary user code
- deploy validators
- manage local environments

At MVP stage:
the backend ONLY validates deterministic outcomes.

---

# Product Goal

The MVP goal is:
# fully functional exploit learning loop.

If users can:
- solve levels
- verify success
- progress naturally

then the core gameplay loop is validated.