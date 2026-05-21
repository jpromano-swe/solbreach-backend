
# SolBreach Future Platform Roadmap

# Objective

This document explains the long-term product direction of SolBreach.

This is NOT an implementation specification.

Its purpose is to:
- align architecture decisions
- preserve future extensibility
- communicate product evolution

---

# Product Vision

SolBreach is evolving into:
# adversarial security training infrastructure for Solana.

The platform is designed to progressively transition users from:
- exploit learners
to:
- independent security researchers.

---

# Platform Stages

# 1. Vulnerabilities

Current MVP focus.

Purpose:
- teach exploit primitives
- build attacker mindset
- understand Solana vulnerabilities

Examples:
- fake mint exploits
- unchecked CPI
- authority spoofing
- PDA misuse

These environments are:
- highly guided
- deterministic
- beginner-friendly

---

# 2. Research Labs

Future expansion.

Purpose:
- simulate realistic investigation workflows
- introduce repository interaction
- expose users to real protocol structures

Research Labs should feel:
# investigative rather than puzzle-based.

Users may:
- inspect repositories
- analyze tests
- reproduce exploits
- interact with realistic environments

These environments remain:
- structured
- educational
- approachable

Research Labs are intended to bridge:
- vulnerability learning
and
- independent research.

---

# 3. Breach Rooms

Advanced future environments.

Purpose:
- simulate realistic adversarial research
- introduce ambiguity and pressure
- develop researcher intuition

Characteristics:
- larger codebases
- incomplete information
- multiple attack surfaces
- limited hints
- realistic audit conditions

Breach Rooms represent:
# advanced security capability training.

---

# Future Platform Systems

Potential future systems:
- sandbox orchestration
- ephemeral lab environments
- certification minting
- researcher reputation systems
- audit competitions
- hiring integrations
- leaderboard systems

---

# Important Architectural Principle

The backend should remain:
# modular and extensible.

Future systems should integrate without requiring:
- major rewrites
- architecture replacement
- business logic duplication

---

# Current MVP Priority

The current focus is:
# validating the exploit learning loop.

NOT:
- full sandbox infrastructure
- distributed systems
- blockchain minting
- advanced orchestration

The priority is:
- user progression
- deterministic verification
- gameplay reliability
- clean extensibility