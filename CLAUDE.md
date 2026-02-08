# Littera Agent Guide

This document exists to guide automated agents and contributors working on the Littera codebase.

It encodes architectural intent, constraints, and non‑obvious project values.

---

## Prime Directive

**Do not break the model.**

The structural and semantic models described in `MANIFESTO.md` are stable by design. Changes that undermine them are considered regressions, even if tests pass.

---

## Stable Concepts

The following are intentionally stable:

- `Work → Document → Section → Block`
- Global entities with work‑specific overlays
- Mentions binding entities to blocks
- Local‑first embedded database
- CLI as authoritative interface

If you feel pressure to weaken these, stop and reconsider the design.

---

## Interface Hierarchy

- CLI defines truth
- TUI exposes structure and meaning
- Desktop app prioritizes immersion

No interface may silently diverge from the model.

---

## Testing Requirements

- No mocks for core behavior
- Use the real embedded PostgreSQL instance
- Black‑box CLI tests preferred

If something is difficult to test, the design likely needs simplification.

---

## Coding Style

- Prefer explicit state over implicit behavior
- Avoid clever abstractions
- Refactor early, not late
- Keep changes minimal and focused

Boring code is a feature.

---

## Design Principles

These apply universally. Any change to any part of the system must respect all of them.

- Editing never breaks structure
- All edits are representable via CLI
- Semantics remain explicit
- Metadata is hidden, not destroyed
- Structure persists invisibly
- Writing flow is prioritized
- Actively resist accidental model erosion and UI‑only state
- Performance at large scale
- Migration and evolution paths must exist
- Export and archival formats are required
- No mandatory cloud services
- Longevity is a feature

---

## When in Doubt

Ask:
- Does this preserve meaning?
- Does this scale to years of writing?
- Would this still make sense after a long break?

If not, rethink the approach.

---

## Closing

Littera is built for durability, not novelty.
Respect that.
