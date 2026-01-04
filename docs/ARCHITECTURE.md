# Littera Architecture

This document defines the **non-negotiable architectural decisions** of Littera.
If something here seems inconvenient later, stop and reconsider before changing it.

---

## 1. Core Abstractions

### Work
Top-level intellectual artifact.
- Language-agnostic
- Stable identity

### Document
Structured text unit inside a Work.
- A book, article, or major part

### Section
Hierarchical container (chapters, sections, subsections).

### Block
Atomic editable unit.
- Paragraphs, lists, code blocks, equations, tables, media
- Language-specific

### Semantic Entity
Represents meaning, not text.
- Characters, concepts, places, people, terms, references
- Exists independently of mentions

### Mention
A textual reference to an entity inside a block.
- Disposable
- Language-specific

---

## 2. Stability Rules

### Stable (Never Change IDs)
- Work
- Document
- Section
- Block
- Semantic Entity

### Derived (Rebuild Anytime)
- Mentions
- Alignments
- Morphological variants
- Embeddings
- LLM suggestions

---

## 3. Storage Model

- **Markdown**: canonical storage for prose
- **Postgres**: canonical storage for identity, structure, and relationships

Markdown must remain readable and editable without Littera.

---

## 4. Linguistics

### Morphology Doctrine (Non‑Negotiable)

> **Entities define constraints, not forms.**

Littera treats morphology like a compiler pass:
- semantic input → deterministic transformation → surface form

#### What entities MAY define
- intrinsic grammatical facts (e.g. gender, animacy)
- irregularity or declension overrides
- author‑asserted constraints

#### What entities MUST NOT store
- declined forms
- generated strings
- language‑specific surface realizations

Those are **derived**, never canonical.

#### Mentions
Mentions specify *intent*, not outcome:
- grammatical role (case, number, possessive, pronoun, etc.)
- local overrides when explicitly authored

Mentions are disposable and may be regenerated at any time.

#### Linguistics layer
All morphology is computed in a deterministic linguistics layer:

```
(entity properties)
+ (mention features)
+ (language rules)
→ surface form
```

Caching is allowed only if:
- clearly marked derived
- safe to wipe
- fully reproducible

#### Language implementations
- **Polish**: Morfeusz + explicit declension rules
- **English**: rule‑based (possessives, pronouns, plurality)

LLMs:
- may assist in ambiguity resolution
- may explain choices
- must never invent grammar or silently modify text

---

## 5. AI Usage Contract

LLMs are allowed to:
- Suggest entities and tags
- Propose translations and alignments
- Detect inconsistencies
- Explain reasoning

LLMs are never allowed to:
- Commit edits silently
- Override deterministic rules
- Invent facts or grammar

---

## 6. Editing Philosophy

- All changes are previewable
- All changes are explainable
- Nothing is irreversible

Littera optimizes for trust over speed.
