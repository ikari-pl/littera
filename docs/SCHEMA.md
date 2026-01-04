# Database Schema

> **Literature meets refactoring.**
>
> This schema encodes that idea in durable form.

This document defines the **initial Postgres schema** for Littera.
It reflects the conceptual model agreed during design and should be treated as a
*semantic contract*, not just a storage detail.

---

## Guiding Principles

- Stable identities are first-class
- Text is stored in Markdown, not fragmented
- The database stores *meaning, structure, and relationships*
- Derived data can be dropped and rebuilt at any time

---

## 1. Core Identity Tables

### `works`
Represents a top-level intellectual artifact.

- `id` (UUID, PK)
- `created_at` (timestamp, not null)
- `title` (text)
- `description` (text)
- `default_language` (text)
- `metadata` (jsonb)

---

### `documents`
Structured text units inside a work.

- `id` (UUID, PK)
- `work_id` (UUID, FK → works.id, not null)
- `created_at` (timestamp, not null)
- `title` (text)
- `order_index` (integer)
- `metadata` (jsonb)

---

### `sections`
Hierarchical containers (chapters, sections, subsections).

- `id` (UUID, PK)
- `document_id` (UUID, FK → documents.id, not null)
- `parent_section_id` (UUID, FK → sections.id, nullable)
- `created_at` (timestamp, not null)
- `title` (text)
- `order_index` (integer)
- `metadata` (jsonb)

---

### `blocks`
Atomic editable units.

- `id` (UUID, PK)
- `section_id` (UUID, FK → sections.id, not null)
- `created_at` (timestamp, not null)
- `block_type` (text, not null)
- `language` (text, not null)
- `source_text` (text, not null)  -- Markdown
- `metadata` (jsonb)

Notes:
- Blocks are language-specific
- `source_text` is the canonical prose

---

## 2. Semantic Model

### `entities`
Represents semantic entities (meaningful things).

- `id` (UUID, PK)
- `created_at` (timestamp, not null)
- `entity_type` (text, not null)
- `canonical_label` (text)
- `properties` (jsonb)
- `status` (text)
- `notes` (text)

---

### `entity_labels`
Language-specific labels and aliases for entities.

- `id` (UUID, PK)
- `entity_id` (UUID, FK → entities.id, not null)
- `language` (text, not null)
- `base_form` (text, not null)
- `aliases` (jsonb)

Unique constraint:
- (`entity_id`, `language`)

---

### `mentions`
Textual references to semantic entities.

- `id` (UUID, PK)
- `block_id` (UUID, FK → blocks.id, not null)
- `entity_id` (UUID, FK → entities.id, not null)
- `language` (text, not null)
- `features` (jsonb)   -- case, number, pronoun, etc.
- `surface_form` (text)

Notes:
- Mentions are disposable
- Mentions may be regenerated

---

## 3. Cross-Language Alignment (Derived)

### `block_alignments`
Logical relationships between blocks in different languages.

- `id` (UUID, PK)
- `source_block_id` (UUID, FK → blocks.id, not null)
- `target_block_id` (UUID, FK → blocks.id, not null)
- `alignment_type` (text)
- `confidence` (numeric)
- `created_at` (timestamp)

Notes:
- Many-to-many allowed
- Rebuildable at any time

---

## 4. Review & Diagnostics (Derived)

### `reviews`
Stores review findings and explanations.

- `id` (UUID, PK)
- `work_id` (UUID, FK → works.id)
- `scope` (text)  -- work, document, section, block
- `scope_id` (UUID)
- `issue_type` (text)
- `description` (text)
- `severity` (text)
- `metadata` (jsonb)
- `created_at` (timestamp)

---

## 5. Explicit Non-Goals (Schema)

This schema intentionally does NOT store:
- Embeddings
- LLM prompts or raw outputs
- Morphological caches
- Generated translations

Those belong in rebuildable layers.

---

## Final Note

If you are tempted to add a table:
- Ask whether it represents **stable identity** or **derived convenience**
- If derived, it probably does not belong here

This schema exists to make large-scale textual refactoring *safe*.
