# Littera

**Littera is a local‑first writing system for serious, long‑form thinking.**

It is designed for works that evolve over years: essays, books, research corpora, and philosophical projects. Littera treats writing not as a stream of text, but as a structured, semantic body of work.

This project is intentionally opinionated, architecturally conservative, and quietly ambitious.

---

## Core Ideas

- Writing has **structure**: `Work → Document → Section → Block`
- Meaning is separate from text via **global entities** and **mentions`
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

- **Desktop App (Planned)** — Immersive writing
  - WYSIWYG‑leaning
  - Metadata largely hidden by default
  - Structure and semantics preserved invisibly
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

Littera is early, but its foundations are in place:

- Embedded PostgreSQL (local, real, tested)
- Structured writing model
- Global semantic entities with work‑specific overlays
- Authoritative CLI
- Functional TUI foundation
- Black‑box tests with no mocks

The next major milestone is a **desktop writing application** that brings Littera’s model into a fluid, distraction‑free environment.

---

## Philosophy

The full philosophy, design principles, and long‑term guarantees of Littera are documented in:

👉 **`MANIFESTO.md`**

If you are considering contributing, extending, or seriously using Littera, read it first.

---

## License

TBD
