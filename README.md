# Littera

**Littera is a local‑first writing system for serious, long‑form thinking.**

It is designed for works that evolve over years: essays, books, research corpora, and philosophical projects. Littera treats writing not as a stream of text, but as a structured, semantic body of work.

This project is intentionally opinionated, architecturally conservative, and quietly ambitious.

---

## Core Ideas

- Writing has **structure**: `Work → Document → Section → Block`
- Meaning is separate from text via **global entities** and **mentions**
- The system is **local‑first** and uses a real embedded database
- Multiple interfaces serve different modes of thinking
- Correct architecture matters more than feature velocity

These ideas are stable and form the long‑term contract of the project.

---

## Interfaces

Littera is intentionally multi‑interface. Each interface optimizes for a different cognitive mode.

- **CLI** — The source of truth
  - Scriptable, idempotent, fully test‑covered
  - Expresses the complete model without abstraction

- **TUI** — Semantic navigation and focused editing
  - Structure‑first exploration
  - Meaning made visible
  - Keyboard‑driven, mode‑aware

- **Desktop App** — Immersive writing
  - Tauri shell with Python sidecar and embedded PostgreSQL
  - ProseMirror rich‑text editor with block‑level structure
  - Entity mentions, slash commands, bubble toolbar
  - Work directory picker with recent works and workspace support
  - Designed for flow, not administration

The CLI defines reality. Other interfaces translate it.

---

## What Littera Is (and Is Not)

Littera is:
- a writing system, not a note app
- built for refactoring thought, not dumping text
- calm, explicit, and durable by design

Littera is not:
- a markdown editor with plugins
- a fragile WYSIWYG document format
- an AI writing assistant
- a cloud‑first or sync‑dependent app

---

## Project Status

Littera's core is stable and all three interfaces are functional:

- Embedded PostgreSQL (local, real, tested)
- Structured writing model (`Work → Document → Section → Block`)
- Global semantic entities with work‑specific overlays
- Authoritative CLI with full model coverage
- TUI for semantic navigation and keyboard‑driven editing
- Desktop app with rich‑text editor, entity mentions, and work picker
- Black‑box CLI tests with no mocks; Playwright test suite for the desktop app

---

## Philosophy

The full philosophy, design principles, and long‑term guarantees of Littera are documented in:

👉 **`MANIFESTO.md`**

If you are considering contributing, extending, or seriously using Littera, read it first.

---

## License

TBD
