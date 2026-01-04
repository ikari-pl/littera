# Linguistics Module

This document specifies the **linguistics subsystem interface**.
It is intentionally language‑agnostic at the core and language‑specific at the edges.

---

## Purpose

The linguistics module:
- generates surface forms deterministically
- validates grammatical correctness
- explains its decisions

It never defines meaning.

---

## Inputs

### Required
- `entity`
  - semantic properties (gender, animacy, overrides)
- `entity_label`
  - language‑specific base form
- `mention_features`
  - grammatical intent (case, number, role, pronoun, possessive)
- `language`

### Optional
- surrounding context (sentence, paragraph)
- user overrides

---

## Outputs

### Primary
- `surface_form` (string)

### Secondary (for editor / review)
- explanation (human‑readable)
- confidence / ambiguity flags
- alternative forms (if ambiguous)

---

## Core Interface (Conceptual)

```
generate_form(
  entity,
  entity_label,
  mention_features,
  language,
  context=None
) -> LinguisticResult
```

Where `LinguisticResult` contains:
- `text`
- `explanation`
- `warnings`

---

## Polish Implementation Notes

- Use Morfeusz as the primary analyzer
- Validate generated forms against Morfeusz output
- Prefer deterministic rules over probabilistic guesses
- Surface ambiguity explicitly to the user

---

## English Implementation Notes

- Handle possessives (`Anna’s`, `James’`)
- Handle pronouns (subject, object, possessive adjective, possessive noun)
- Handle pluralization

---

## Caching Policy

- Caches are optional
- Caches must be disposable
- Caches must never be treated as canonical data

---

## Non‑Goals

The linguistics module does NOT:
- rewrite prose
- guess authorial intent
- commit edits
- store canonical data

It exists to make refactoring **safe and explainable**.
