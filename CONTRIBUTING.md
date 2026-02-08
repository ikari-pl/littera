# Contributing to Littera

Littera is built for durability. Contributions are welcome, but they must respect the project's design constraints and long-term intent.

Before making changes, read this document fully.

---

## Required Reading

These documents define the project. Changes that conflict with them will not be accepted.

- **`MANIFESTO.md`** -- Project philosophy, design ethos, and stability guarantees
- **`INVARIANTS.md`** -- What must not change and why
- **`AI.md`** -- Constraints for automated agents (applies equally to human contributors)

If you have not read these, you are not ready to contribute.

---

## The Model

Littera's structural and semantic model is intentionally stable:

```
Work -> Document -> Section -> Block
```

- Entities are global. Mentions bind entities to blocks.
- Structure and meaning are distinct layers.
- Local-first embedded PostgreSQL is required, not optional.

Changes that weaken, blur, or shortcut this model are regressions, regardless of whether tests pass.

---

## Interface Hierarchy

Each interface serves a different cognitive mode. They are not interchangeable.

- **CLI** defines truth. Every operation must be representable here.
- **TUI** exposes structure and meaning. Keyboard-driven, mode-aware.
- **Desktop app** prioritizes immersion. Structure persists beneath the surface.

No interface may silently diverge from the CLI model. UI-only state is not permitted.

---

## Development Setup

Littera requires Python 3.11+ and an embedded PostgreSQL instance for development and testing.

See `DEVELOPMENT.md` for full setup and build instructions.

The database schema lives in `db/schema.sql`. The embedded PostgreSQL lifecycle is managed by the code in `src/littera/db/`.

---

## Coding Conventions

- Prefer explicit state over implicit behavior
- Avoid clever abstractions
- Refactor early, not late
- Keep changes minimal and focused

Boring code is a feature. If Littera ever feels clever, something has gone wrong.

Choose the solution that will still make sense in five years.

---

## Testing

Tests are not optional. They function as executable documentation and design enforcement.

### Requirements

- **No mocks for core behavior.** Use the real embedded PostgreSQL instance.
- **Black-box CLI tests preferred.** Test through the CLI interface, not internal APIs.
- **If something is difficult to test, the design likely needs simplification.**

### Test Structure

- `tests/` -- CLI and core model tests (pytest)
- `tests/tui/` -- TUI-specific tests
- `desktop/tests/` -- Playwright tests for the desktop app

Run the core test suite:

```
pytest tests/
```

### What Tests Must Verify

Tests encode invariants, not just outcomes. A test that passes while an invariant is violated is a false positive, not a success.

---

## Making Changes

### Before You Start

Ask yourself:

- Does this preserve meaning?
- Does this scale to years of writing?
- Would this still make sense after a long break?

If not, rethink the approach.

### Pull Requests

- Keep changes minimal and focused. One concern per PR.
- Explain the "why," not just the "what."
- Include tests. Changes without tests are incomplete.
- Ensure all existing tests continue to pass.

### What Not to Do

The following are disallowed unless the project's foundational documents are explicitly revised:

- Removing or flattening structure for convenience
- "For now" shortcuts that become permanent
- UI-driven schema changes
- Replacing the database with files or JSON
- Introducing implicit magic or hidden state
- Making AI-generated text a core dependency
- Replacing explicit commands with implicit behavior
- Optimizing for speed at the cost of meaning

If you find yourself proposing one of these, stop and reconsider.

---

## When in Doubt

If your change does not clearly strengthen the model, it probably weakens it.

When uncertain, open an issue describing your intent before writing code. Discussion is cheaper than reverting.

---

## Closing

Littera assumes serious users, long timelines, and evolving understanding.

Contributions that share these assumptions are valued.
