# Phase 1A — Core Semantic Editing (Schema + CLI)

## Goal

Make the model *real* and *trustworthy* via schema + CLI commands.

This phase exists to prevent UI churn from destabilizing the project: if it isn't expressible and testable in CLI, it isn't "true".

## Scope

- Schema represents the model and invariants
- CLI defines authoritative behavior for:
  - structure management (documents/sections/blocks)
  - block editing
  - entities + work overlays (notes)
  - mentions (entity ↔ block)
- Black-box CLI tests against real embedded Postgres

## Non-Goals

- TUI features / UX polish
- Desktop app

## Current Status (2026-02-07)

✅ **COMPLETE** — All checklist items done. CLI covers full model CRUD including entities, labels, mentions, alignments, and reviews. Black-box test suite runs against real embedded Postgres.

## Can Start / Can Ship

### Can Start (Prerequisites Checklist)

Core work can start once the agent has confirmed:

- [x] The model invariants are understood (`MANIFESTO.md`, `INVARIANTS.md`).
- [x] A work directory exists (or can be created) with `.littera/config.yml`.
- [x] Embedded Postgres can start in that work and the DB connection succeeds.
- [x] Schema can be applied (or verified) from `db/schema.sql`.

**Stop condition**

- If embedded Postgres cannot start / connect, stop and fix DB bootstrap path first (no feature work).

### Can Ship

- Core features can ship when the behavior is covered by black-box CLI tests using the real embedded Postgres.

## Gating Rules

- All meaning-changing behavior lands here first.
- Any UI feature that writes to DB must have a corresponding CLI command and test.

## Checklist

### A. Model + Schema

- [x] Confirm schema tables cleanly represent:
  - [x] documents / sections / blocks
  - [x] entities / labels
  - [x] work overlays (entity_work_metadata)
  - [x] mentions (block_id, entity_id, language)
  - [x] Add DB constraints that prevent illegal states (where feasible)
  - [x] Add indexes for common lookups:
    - [x] blocks by section
    - [x] sections by document
    - [x] mentions by entity_id / block_id

### B. CLI (Authoritative Interface)

- [x] Editing commands
  - [x] edit block text (create/update)
  - [x] edit work-scoped entity note
  - [x] Navigation / structure commands
    - [x] create document / section / block
    - [x] list documents / sections / blocks
    - [x] delete document / section / block (with guards)
    - [x] edit titles (document/section)
  - [x] Mention commands
    - [x] link entity to block
    - [x] list mentions by entity
    - [x] list mentions by block
  - [x] Error handling
    - [x] predictable, CLI-friendly errors
    - [x] no silent behavior changes

### C. CLI Tests (Black-Box Preferred)

- [x] Create a minimal work fixture
- [x] Run tests against real embedded Postgres
- [x] Add tests for:
  - [x] creating and listing docs/sections/blocks
  - [x] editing block text
  - [x] editing work-scoped entity note
  - [x] linking mentions
  - [x] guards (deleting non-empty structures, invalid ids)

## Parallelizable Work

This phase is a dependency for everything else, but can be executed in parallel with UI prototyping as long as:

- UI work does not define new semantics
- any new behavior lands here first (CLI + tests)

## Exit Criteria

- CLI can fully create, inspect, and edit the model.
- Mentions + overlays are correct and queryable.
- A black-box test suite proves the above on real embedded Postgres.