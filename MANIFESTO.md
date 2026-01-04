# Littera Manifesto

## What Littera Is

**Littera is a local‑first writing system for serious, long‑form thinking.**

It exists for work that cannot be rushed: essays that mature, books that change shape, research that accretes meaning over time. Littera treats writing as an evolving system rather than a flat document.

It is deliberately built closer to a database and a compiler than to a text editor.

And yes — we are slightly proud of this.

---

## The Stable Core

Certain ideas in Littera are intended to remain stable over time. They are the project’s backbone.

### Structural Model

Writing is organized as:

```
Work → Document → Section → Block
```

- **Work**: a bounded intellectual universe
- **Document**: a coherent piece within a work
- **Section**: structural grouping
- **Block**: the smallest meaningful unit of text

Blocks are intentionally small. They are the unit of reference, editing, and semantic attachment.

---

### Semantic Model

Text and meaning are not the same thing.

- **Entities** represent concepts, people, places, works, or ideas
- Entities are **global**, not owned by a single work
- **Mentions** bind entities to specific blocks
- Entities support:
  - multilingual labels
  - work‑specific notes
  - multiple mentions across documents

This enables conceptual refactoring without rewriting prose and preserves meaning even as text evolves.

This is not tagging. It is a lightweight, intentional knowledge graph embedded in writing.

---

## Local‑First by Design

Littera is local‑first as a principle, not a feature.

- All data lives on your machine
- Uses a real embedded PostgreSQL instance
- No accounts
- No required network access
- No silent synchronization

If networked features ever exist, they must be additive and optional.

---

## Interfaces as Cognitive Tools

Littera is intentionally multi‑interface. Each interface serves a distinct mode of thought.

### CLI — Authority and Precision

- Defines the complete model
- Scriptable and idempotent
- Fully test‑covered

If something cannot be done via CLI, it does not exist yet.

---

### TUI — Semantic Navigation

- Structure‑first exploration
- Meaning made visible
- Keyboard‑driven
- Mode‑aware editing

The TUI makes large works legible without hiding their structure.

---

### Desktop App — Immersive Writing (Planned)

The desktop application is a core goal, not an afterthought.

It is intended to be:
- WYSIWYG‑leaning
- calm and immersive
- largely free of visible metadata

Structure and semantics persist invisibly beneath the surface. Writers should be able to enter flow without managing machinery.

The desktop app is where Littera becomes transformative rather than merely powerful.

---

## Architecture Before Features

Littera prefers:
- explicit state
- boring solutions
- clear lifecycles
- early refactoring

Feature velocity is secondary to correctness. If something is hard to test, the design is suspect.

---

## Tests as Philosophy

Tests are not optional.

- No mocks for core behavior
- Real embedded database
- Black‑box CLI tests

Tests function as executable documentation and design enforcement.

---

## What Littera Is Not

Littera is not:
- a note‑taking app
- a markdown experiment
- a fragile WYSIWYG document format
- an AI writing assistant
- a cloud‑first collaboration platform

---

## Stability Guarantees

The following are intended to remain stable:

- Structural hierarchy
- Global entities with work‑specific overlays
- Local‑first storage
- CLI authority
- No forced cloud dependency

Interfaces may evolve. The model should not.

---

## Design Ethos

Writing is thinking made persistent.

Structure is a tool, not a constraint.
Refactoring is a literary act.

Littera assumes serious users, long timelines, and evolving understanding.

If Littera ever feels clever, something has gone wrong.

---

## FAQ

### Why PostgreSQL for a local tool?
Because correctness matters. A real database provides durability, constraints, migrations, and semantic clarity that file formats eventually reinvent poorly.

### Why blocks instead of paragraphs or pages?
Blocks are the smallest unit that can carry meaning, references, and intent without becoming unwieldy.

### Why a desktop app if the CLI is authoritative?
Because different cognitive modes require different interfaces. Authority and immersion are not the same thing.

### Will the desktop app hide the structure?
It will hide the machinery, not the meaning. Structure remains present and recoverable.

### Will this ever be cloud‑based?
Not by default. Local‑first is a design constraint, not a phase.

### Is Littera for everyone?
No. It is intentionally opinionated. It is for people whose writing benefits from structure, refactoring, and semantic clarity.

---

## Closing

Littera exists because long‑form thinking deserves tools that do not decay under seriousness.

It is built to last.
