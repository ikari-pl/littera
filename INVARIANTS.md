# Littera Invariants

This document exists to lock the model.

It is written for humans, but intended to be enforced culturally, architecturally, and through tests.

---

## Purpose

Littera is designed to support writing that lasts years or decades.

This requires resisting certain classes of "improvements" that feel productive in the short term but corrode meaning over time.

These invariants define what must not change lightly.

---

## Structural Invariants

- Writing is always structured as:
  `Work → Document → Section → Block`
- Blocks are the smallest meaningful unit
- Blocks are the unit of reference, mention, and editing

Violations:
- treating paragraphs, pages, or files as atomic units
- allowing free‑floating text outside blocks

---

## Semantic Invariants

- Entities are global
- Entities are not owned by a single work
- Mentions bind entities to blocks
- Meaning is not inferred implicitly from text

Violations:
- auto‑creating entities without intent
- hiding semantic state inside prose

---

## Interface Invariants

- CLI is authoritative
- Every operation must be representable via CLI
- Other interfaces may hide complexity, not invent it

Violations:
- UI‑only state
- behavior impossible to script

---

## Storage Invariants

- Local‑first is mandatory
- Real embedded PostgreSQL is required
- No silent sync or cloud assumptions

Violations:
- replacing DB with files
- requiring accounts or network access

---

## Testing Invariants

- Core behavior is tested without mocks
- Tests encode invariants, not just outcomes

If an invariant cannot be tested, it should be questioned.

---

## When Change Is Allowed

Change is permitted when:
- the invariant is explicitly revised
- the cost is acknowledged
- migrations are provided
- the long‑term model is strengthened

Change is not permitted by accident.

---

## Closing

These invariants exist to protect meaning.

Break them only with intent.
