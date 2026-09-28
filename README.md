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
  - Import/export (JSON and Markdown)

- **TUI** — Semantic navigation and focused editing
  - Structure‑first exploration with drill‑down outline
  - Entity labels, properties, mentions, and surface forms
  - Alignment CRUD with gap detection
  - Keyboard‑driven: 70+ bindings, inline rename, reordering

- **Desktop App** — Immersive writing
  - Tauri shell with Python sidecar and embedded PostgreSQL
  - ProseMirror rich‑text editor with block‑level structure
  - Entity mentions, slash commands, bubble toolbar
  - Command palette, theme toggle, distraction‑free mode
  - Work directory picker with recent works and workspace support
  - Alignment gap detection and inflect preview
  - Import/export via sidecar API

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

Littera's core is stable and all three interfaces have near‑complete feature parity:

- Embedded PostgreSQL (local, real, tested)
- Structured writing model (`Work → Document → Section → Block`)
- Global semantic entities with labels, properties, and work‑scoped notes
- Entity mentions with language‑aware surface form generation (English morphology engine)
- Block alignments with cross‑language gap detection
- Reviews with severity and scope
- Document and section reordering across all interfaces
- Import/export in JSON and Markdown formats
- Black‑box CLI tests with no mocks; Playwright test suite for the desktop app

---

## Quick Start

```
git clone <repo-url> littera
cd littera
uv venv
uv pip install -e .

littera init my-novel
cd my-novel

littera doc add "Chapter One"
littera section add 1 "Opening"
littera block add 1 "It was a dark and stormy night." --lang en
littera doc list

littera tui          # structure-first navigation
# or open the desktop app from desktop/
```

Forgot the model? In the TUI press `?`. In the desktop app press `Cmd+/` or click **?**.

Full setup notes (Postgres binaries, Tauri, tests): **`DEVELOPMENT.md`**.

---

## Philosophy

The full philosophy, design principles, and long‑term guarantees of Littera are documented in:

👉 **`MANIFESTO.md`**

If you are considering contributing, extending, or seriously using Littera, read it first.

---

## License

TBD
