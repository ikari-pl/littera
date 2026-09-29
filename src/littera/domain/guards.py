"""Domain guards: rules every writing interface must obey.

Each guard raises :class:`GuardViolation` with a message that is safe to show
to a user.  Callers decide how to present it — the CLI prints it and exits,
the TUI shows a notification — but none of them may skip it.
"""

from __future__ import annotations

import uuid


class GuardViolation(RuntimeError):
    """A write was refused because it would break a domain rule."""


def ensure_alignment_languages_differ(
    source_language: str, target_language: str
) -> None:
    """Refuse an alignment between two blocks in the same language.

    An alignment records that two blocks say the same thing in different
    languages.  Two blocks in one language are not an alignment.
    """
    if source_language == target_language:
        raise GuardViolation(
            f"Cannot align blocks in the same language ({source_language})"
        )


def find_entity(cur, entity_type: str, name: str) -> str | None:
    """Return the id of a global entity, or None when it does not exist."""
    cur.execute(
        "SELECT id FROM entities WHERE entity_type = %s AND canonical_label = %s",
        (entity_type, name),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def ensure_entity_exists(cur, entity_type: str, name: str) -> str:
    """Return the entity id, refusing to invent an entity that does not exist.

    Entities are created with intent (INVARIANTS.md: "auto-creating entities
    without intent" is a violation), so binding a mention to an unknown
    entity is refused rather than silently creating one.
    """
    entity_id = find_entity(cur, entity_type, name)
    if entity_id is None:
        raise GuardViolation(f"Entity not found: {entity_type} {name}")
    return entity_id

# Reviews -----------------------------------------------------------------

VALID_SCOPES = frozenset(
    {"work", "document", "section", "block", "entity", "alignment"}
)

_SCOPE_TABLES = {
    "work": "works",
    "document": "documents",
    "section": "sections",
    "block": "blocks",
    "entity": "entities",
    "alignment": "block_alignments",
}


def ensure_review_scope(cur, scope: str | None, scope_id: str | None) -> None:
    """Refuse a review whose scope does not name a row that exists.

    `reviews.scope_id` carries no foreign key (it is polymorphic), so nothing
    in the schema stops a review pointing at a deleted or wrong-typed row.
    Every interface must check it here instead.
    """
    if scope is None:
        return
    if scope not in VALID_SCOPES:
        raise GuardViolation(
            f"Invalid scope: {scope} (must be one of: {', '.join(sorted(VALID_SCOPES))})"
        )
    if scope == "work" or scope_id is None:
        return
    # Parse before querying: a malformed uuid sent to Postgres aborts the
    # surrounding transaction, and a refusal must not poison the caller's
    # connection.
    try:
        uuid.UUID(str(scope_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise GuardViolation(f"Invalid {scope} id: {scope_id}") from exc
    table = _SCOPE_TABLES[scope]
    cur.execute(f"SELECT 1 FROM {table} WHERE id = %s", (scope_id,))
    if cur.fetchone() is None:
        raise GuardViolation(f"No {scope} with id {scope_id}")


def block_language(cur, block_id: str) -> str:
    """Return a block's language, refusing ids that name no block."""
    cur.execute("SELECT language FROM blocks WHERE id = %s", (block_id,))
    row = cur.fetchone()
    if row is None:
        raise GuardViolation(f"No block with id {block_id}")
    return str(row[0])


def ensure_blocks_alignable(cur, source_block_id: str, target_block_id: str) -> None:
    """Refuse an alignment whose two blocks share a language."""
    ensure_alignment_languages_differ(
        block_language(cur, source_block_id),
        block_language(cur, target_block_id),
    )
