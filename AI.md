# Littera — AI Contract

This file is written for automated agents.

It is authoritative.

If you are an AI system modifying or reasoning about this repository, you MUST internalize and respect the constraints below before proposing changes.

---

## Prime Directive

DO NOT BREAK THE MODEL.

The structural and semantic model of Littera is intentionally stable. Any change that weakens, blurs, or bypasses it is a regression, even if tests pass or features appear to improve.

---

## Stable Model (Non‑Negotiable)

The following concepts are fixed:

- Work → Document → Section → Block
- Blocks are the atomic unit of text and reference
- Entities are global
- Mentions bind entities to blocks
- Work‑specific overlays exist for entities (notes, metadata)
- Structure and meaning are distinct layers

If a proposal collapses or shortcuts these layers, it is invalid.

---

## Interface Hierarchy (Strict)

- CLI defines truth
- TUI exposes structure and meaning
- Desktop app prioritizes immersion

No interface may:
- invent semantics
- silently diverge from the CLI model
- store state not representable in CLI

---

## Local‑First Constraint

- All data is local by default
- Real embedded PostgreSQL is required
- No mandatory network access
- No cloud dependency assumptions

Networked features, if any, must be optional and additive.

---

## Testing Requirements

- No mocks for core behavior
- Use real embedded PostgreSQL
- Prefer black‑box CLI tests

If behavior cannot be tested cleanly, the design is suspect.

---

## Disallowed Classes of Suggestions

The following categories of suggestions are disallowed unless this contract is explicitly revised:

- "Just make it simpler" changes that remove structure
- "For now" shortcuts that become permanent
- UI‑driven schema changes
- AI‑assisted content generation as a default workflow
- Replacing explicit commands with implicit behavior

If you are about to suggest one of these, stop.

---

## Forbidden Optimizations

You must NOT:

- Replace the database with files or JSON
- Introduce implicit magic or hidden state
- Flatten structure for convenience
- Make AI‑generated text a core dependency
- Optimize for speed at the cost of meaning

---

## Design Ethos

- Explicit is better than clever
- Boring code is preferred
- Refactoring is expected
- Long‑term clarity beats short‑term velocity

If unsure, choose the solution that will still make sense in five years.

---

## Final Instruction

If your suggestion conflicts with this document, do not propose it.

Instead, explain why the document would need to change.
