# Phase 1B — TUI Layer (Structure + Meaning)

## Goal

Provide a stable, fast TUI that exposes the model defined by Phase 1A.

This phase explicitly does *not* define new semantics. It should be able to "lag" the CLI without blocking core progress.

## Dependencies

- Requires Phase 1A for authoritative semantics.
- Any new behavior discovered while building the TUI must be implemented in Phase 1A (CLI + tests) before being considered complete here.

## Can Start / Can Ship

### Can Start (Prerequisites Checklist)

TUI work can start once all of the following are true:

- [x] A work directory can be opened (a `.littera/config.yml` exists).
- [x] Embedded Postgres can start and the DB connection succeeds.
- [x] The schema is applied and core tables exist.
- [x] The model is readable end-to-end:
  - [x] list documents
  - [x] list sections for a document
  - [x] list blocks for a section

Practical proof:

- [x] You can run `python -m littera.tui.app` inside a work dir and see the document list without crashing.

### Can Ship

- **Can ship (write paths)**: only when the equivalent behavior exists in Phase 1A CLI + tests.
- **Can ship (read-only UX)**: anytime, if it doesn't introduce new semantics.

## Gating Rules

- No UI-only meaning: if a TUI flow changes data, it must map to existing CLI semantics.
- When a TUI bug reveals an ambiguous rule, the rule must be decided in Phase 1A (CLI truth), then reflected here.
- Regressions should become interaction tests before fixes (when feasible).

## Current Status (2026-01-10)

✅ **COMPLETE**

- Done: reducer-style state (`dispatch(Action)`) and explicit view contexts
- Done: Textual stability hardening:
  - async re-render (prevents duplicate-id crashes)
  - UUID-safe widget ids (prefixed)
  - avoid highlight-triggered rerender loops
- Done: TUI mention linking aligns with schema `(block_id, entity_id, language)`
- Done: Formal `reduce(state, action)` function extracted to state.py
- Done: Computed properties on AppState (edit_session, entity_selection, nav_level, etc.)
- Done: Bug burn-down complete (UUID selector comparison bug fixed)
- Tests: `pytest -q tests/tui` passes (25 tests)
- Tests: Full suite passes (44 tests)

## Progress Summary

- **Navigation UX (Outline)**: ✅ COMPLETE
- **Entities UX**: ✅ COMPLETE
- **Editing**: ✅ COMPLETE
- **Mentions**: ✅ COMPLETE
- **TUI Tests**: ✅ COMPLETE
- **State Machine**: ✅ COMPLETE (formalized reducer pattern)
- **Bug Burn-Down**: ✅ COMPLETE (no known issues)

## Checklist

### A. State + Rendering Architecture

- [x] Single reducer-style API (`dispatch(Action)`)
- [x] Base contexts (`outline`, `entities`) plus editor overlay
- [x] Editor overlay cannot exist without session
- [x] Async view re-rendering (no duplicate ids)
- [x] Widget-id encoding/decoding for UUIDs

### B. Navigation UX (Outline)

- [x] Left pane lists current level (docs → sections → blocks) reliably
- [x] Right pane shows detail for selection
- [x] Highlight updates detail without drill-down
- [x] Activate (Enter/click) drills down to next level
- [x] Back pops outline path

### C. Entities UX

- [x] Entity list with stable selection
- [x] Entity detail: labels, mentions, and work-scoped note
- [x] Navigation between outline and entities without losing context unexpectedly

### D. Editing

- [x] Block edit opens editor overlay
- [x] Entity note edit opens editor overlay
- [x] Save writes to DB and returns to prior base context
- [x] Undo/redo scoped to current edit session

### E. Mentions

- [x] Link entity to selected block (schema-correct)
- [x] Provide a UI flow that makes linking discoverable and hard to misuse

### F. TUI Tests

- [x] Unit tests for state reducer actions
- [x] Textual pilot tests for crash resilience
- [x] Interaction test: drill-down changes left list contents
- [x] Interaction test: editor open/save/back returns correctly

### G. Bug Burn-Down

- [x] Add a "known issues" list (short-lived, deleted when empty) — None needed; no known issues
- [x] Convert regressions into tests before fixing — UUID selector bug captured in test_block_create_with_uuid_selector

## Parallelizable Work

This phase can run in parallel with Phase 1A if it stays within these constraints:

- no new meaning is introduced in the TUI
- any discovered semantic gap becomes a Phase 1A task

## Exit Criteria

- TUI is stable enough for day-to-day navigation and editing.
- TUI behavior matches CLI truth.
- The majority of regressions are covered by interaction tests.