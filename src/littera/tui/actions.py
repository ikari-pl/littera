"""DB mutation functions for TUI actions.

All database writes live here. App.py action methods become thin
orchestrators: guard → call actions.py → dispatch state → render.
"""

import json
import uuid
from pathlib import Path

from littera.domain import guards

# =============================================================================
# Creation
# =============================================================================

def create_document(db, work_id: str, title: str) -> str:
    """Create a new document. Returns the new document id."""
    doc_id = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
            (doc_id, work_id, title),
        )
    db.commit()
    return doc_id


def create_section(db, document_id: str, title: str) -> str:
    """Create a new section in a document. Returns the new section id."""
    section_id = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO sections (id, document_id, title, order_index) "
            "VALUES (%s, %s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1))",
            (section_id, document_id, title, document_id),
        )
    db.commit()
    return section_id


def resolve_block_language(cur, section_id: str) -> str:
    """Language a new block in this section should inherit.

    Previous sibling first (the writer is continuing a passage), then the
    work's default language. 'en' only when the work declares nothing.
    """
    cur.execute(
        "SELECT language FROM blocks WHERE section_id = %s "
        "ORDER BY order_index DESC NULLS LAST, created_at DESC LIMIT 1",
        (section_id,),
    )
    row = cur.fetchone()
    if row and row[0]:
        return row[0]

    cur.execute(
        """
        SELECT w.default_language
        FROM sections s
        JOIN documents d ON d.id = s.document_id
        JOIN works w ON w.id = d.work_id
        WHERE s.id = %s
        """,
        (section_id,),
    )
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    return "en"


def create_block(db, section_id: str, language: str | None = None) -> str:
    """Create a new, empty block in a section. Returns the new block id.

    The block starts empty on purpose: a placeholder like '(new block)' would
    count towards the word count and be exported into the compiled manuscript.
    """
    block_id = str(uuid.uuid4())
    with db.cursor() as cur:
        if language is None:
            language = resolve_block_language(cur, section_id)
        cur.execute(
            "INSERT INTO blocks (id, section_id, block_type, language, source_text, order_index) "
            "VALUES (%s, %s, 'paragraph', %s, '', "
            "COALESCE((SELECT MAX(order_index)+1 FROM blocks WHERE section_id = %s), 1))",
            (block_id, section_id, language, section_id),
        )
    db.commit()
    return block_id


def create_entity(db, entity_type: str, name: str) -> str | None:
    """Create a new entity. Returns the entity id, or None on failure."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO entities (entity_type, canonical_label) VALUES (%s, %s) RETURNING id",
            (entity_type, name),
        )
        row = cur.fetchone()
    if row is None:
        return None
    db.commit()
    return str(row[0])


# =============================================================================
# Deletion
# =============================================================================

def create_review(db, work_id: str, description: str, severity: str = "medium",
                  scope: str | None = None, issue_type: str | None = None,
                  scope_id: str | None = None) -> str:
    """Create a new review. Returns the review id.

    Scope is validated against the same set the CLI uses, so the TUI cannot
    write a review the CLI would have refused.
    """
    if scope is None:
        scope_id = None

    review_id = str(uuid.uuid4())
    with db.cursor() as cur:
        # Shared with the CLI and the desktop server: a review may not point
        # at a scope row that does not exist (reviews.scope_id has no FK).
        guards.ensure_review_scope(cur, scope, scope_id)
        cur.execute("""
            INSERT INTO reviews (id, work_id, description, severity, scope, scope_id, issue_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (review_id, work_id, description, severity, scope, scope_id, issue_type))
    db.commit()
    return review_id


def delete_review(db, review_id: str) -> None:
    """Delete a review by its id."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    db.commit()


def update_review(
    db,
    review_id: str,
    description: str | None = None,
    severity: str | None = None,
    scope: str | None = None,
    scope_id: str | None = None,
    clear_scope: bool = False,
) -> None:
    """Update provided review fields.

    ``clear_scope`` nulls both scope columns; ``scope`` must come with a
    ``scope_id``, the same contract the CLI's ``review edit`` enforces.
    """
    from littera.cli.review import apply_review_update

    fields: dict = {}
    if description is not None:
        fields["description"] = description
    if severity is not None:
        fields["severity"] = severity
    if clear_scope:
        fields["clear_scope"] = True
    elif scope is not None:
        fields["scope"] = scope
        fields["scope_id"] = scope_id
    if not fields:
        return
    with db.cursor() as cur:
        apply_review_update(cur, review_id, **fields)
    db.commit()


# =============================================================================
# Deletion and its dependents
# =============================================================================

_DELETE_TABLES = {"document": "documents", "section": "sections", "block": "blocks"}


def _delete_targets(cur, kind: str, item_id: str) -> tuple[list[str], list[str], list[str]]:
    """Ids removed by deleting `item_id`: (documents, sections, blocks).

    The FK cascades in db/schema.sql do this silently; naming the rows first
    is what lets the interface tell the writer what is about to go.
    """
    if kind == "document":
        cur.execute("SELECT id FROM sections WHERE document_id = %s", (item_id,))
        section_ids = [str(r[0]) for r in cur.fetchall()]
        cur.execute(
            "SELECT b.id FROM blocks b JOIN sections s ON s.id = b.section_id "
            "WHERE s.document_id = %s",
            (item_id,),
        )
        return [str(item_id)], section_ids, [str(r[0]) for r in cur.fetchall()]
    if kind == "section":
        cur.execute("SELECT id FROM blocks WHERE section_id = %s", (item_id,))
        return [], [str(item_id)], [str(r[0]) for r in cur.fetchall()]
    if kind == "block":
        return [], [], [str(item_id)]
    return [], [], []


def _dependent_counts(cur, docs: list[str], secs: list[str], blocks: list[str],
                      item_id: str) -> dict:
    """Count what a delete destroys (mentions, alignments) or orphans (reviews)."""
    mentions = 0
    alignments = 0
    if blocks:
        cur.execute(
            "SELECT count(*) FROM mentions WHERE block_id = ANY(%s::uuid[])",
            (blocks,),
        )
        mentions = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM block_alignments "
            "WHERE source_block_id = ANY(%s::uuid[]) OR target_block_id = ANY(%s::uuid[])",
            (blocks, blocks),
        )
        alignments = cur.fetchone()[0]

    all_ids = docs + secs + blocks
    reviews = 0
    if all_ids:
        # reviews.scope_id has no foreign key, so nothing cascades here: a
        # block-scoped review would otherwise point at a row that is gone.
        cur.execute(
            "SELECT count(*) FROM reviews WHERE scope_id = ANY(%s::uuid[])",
            (all_ids,),
        )
        reviews = cur.fetchone()[0]

    return {
        "sections": len([s for s in secs if s != item_id]),
        "blocks": len([b for b in blocks if b != item_id]),
        "mentions": mentions,
        "alignments": alignments,
        "reviews": reviews,
    }


def count_delete_dependents(db, kind: str, item_id: str) -> dict:
    """What deleting this document/section/block would take with it."""
    if kind not in _DELETE_TABLES:
        return {}
    with db.cursor() as cur:
        docs, secs, blocks = _delete_targets(cur, kind, item_id)
        return _dependent_counts(cur, docs, secs, blocks, item_id)


def delete_item(db, kind: str, item_id: str) -> dict:
    """Delete a document, section, or block and resolve its dependents.

    Mentions and block_alignments cascade; reviews do not, so in the same
    transaction every review scoped to a row being deleted has its scope
    cleared. The note itself survives — metadata is hidden, not destroyed.

    Returns the dependent counts that were destroyed or unscoped.
    """
    from littera.cli.review import apply_review_update

    table = _DELETE_TABLES.get(kind)
    if table is None:
        return {}

    with db.cursor() as cur:
        docs, secs, blocks = _delete_targets(cur, kind, item_id)
        counts = _dependent_counts(cur, docs, secs, blocks, item_id)

        all_ids = docs + secs + blocks
        if all_ids:
            cur.execute(
                "SELECT id FROM reviews WHERE scope_id = ANY(%s::uuid[])",
                (all_ids,),
            )
            for (review_id,) in cur.fetchall():
                apply_review_update(cur, str(review_id), clear_scope=True)

        cur.execute(f"DELETE FROM {table} WHERE id = %s", (item_id,))
    db.commit()
    return counts


def delete_entity(db, entity_id: str) -> None:
    """Delete an entity by id. Cascades to mentions and labels via FK."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
    db.commit()


# =============================================================================
# Reordering
# =============================================================================

def move_item(db, kind: str, item_id: str, new_position: int) -> bool:
    """Move a document, section, or block to a new position (1-based).

    Documents reorder among siblings in the same work.
    Sections reorder among siblings in the same document.
    Blocks reorder among siblings in the same section.

    Returns True if the move was applied, False if position is out of range.
    """
    from littera.cli.block import reorder_siblings

    tables = {"document": "documents", "section": "sections", "block": "blocks"}
    table = tables.get(kind)
    if table is None:
        return False

    with db.cursor() as cur:
        ok, _ = reorder_siblings(cur, table, item_id, new_position)
    if not ok:
        return False
    db.commit()
    return True


# =============================================================================
# Updates
# =============================================================================

def update_title(db, kind: str, item_id: str, title: str) -> None:
    """Update title for a document or section."""
    with db.cursor() as cur:
        if kind == "document":
            cur.execute("UPDATE documents SET title = %s WHERE id = %s", (title, item_id))
        elif kind == "section":
            cur.execute("UPDATE sections SET title = %s WHERE id = %s", (title, item_id))
        else:
            return
    db.commit()


def set_block_language(db, block_id: str, language: str) -> None:
    """Update a block's language."""
    with db.cursor() as cur:
        cur.execute("UPDATE blocks SET language = %s WHERE id = %s", (language, block_id))
    db.commit()


# =============================================================================
# Entity linking
# =============================================================================

def find_entities_by_label(db, entity_name: str) -> list[tuple[str, str, str]]:
    """Entities whose canonical label matches, as (id, entity_type, label).

    Matching on the label alone would collide same-label/different-type
    entities, so the type is carried back for the caller to disambiguate.
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, entity_type, canonical_label FROM entities "
            "WHERE canonical_label = %s ORDER BY entity_type",
            (entity_name,),
        )
        return [(str(r[0]), r[1], r[2] or "(unnamed)") for r in cur.fetchall()]


def link_block_to_entity(db, block_id: str, entity_id: str) -> bool:
    """Bind an existing entity to a block. Returns True if a mention was added.

    Never creates an entity: INVARIANTS.md forbids auto-creating entities
    without intent, and the CLI refuses the same way (cli/mention.py).
    """
    with db.cursor() as cur:
        # Block language is required by the mentions schema.
        cur.execute("SELECT language FROM blocks WHERE id = %s", (block_id,))
        lang_row = cur.fetchone()
        if lang_row is None:
            raise LookupError(f"Block {block_id} not found")
        language = lang_row[0]

        cur.execute("SELECT 1 FROM entities WHERE id = %s", (entity_id,))
        if cur.fetchone() is None:
            raise LookupError(f"Entity {entity_id} not found")

        cur.execute(
            "SELECT 1 FROM mentions WHERE block_id = %s AND entity_id = %s AND language = %s",
            (block_id, entity_id, language),
        )
        if cur.fetchone() is not None:
            return False
        cur.execute(
            "INSERT INTO mentions (block_id, entity_id, language) VALUES (%s, %s, %s)",
            (block_id, entity_id, language),
        )
    db.commit()
    return True


# =============================================================================
# Saving edits
# =============================================================================

def save_entity_note(db, entity_id: str, work_id: str, text: str) -> None:
    """Save (upsert) an entity's work-scoped note.

    The overlay is merged, not replaced: overwriting the whole JSONB would
    destroy every other key a CLI command or the desktop app put there.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (entity_id, work_id)
            DO UPDATE SET metadata =
                COALESCE(entity_work_metadata.metadata, '{}'::jsonb) || EXCLUDED.metadata
            """,
            (entity_id, work_id, json.dumps({"note": text})),
        )
    db.commit()


def save_block_text(db, block_id: str, text: str) -> None:
    """Save block source text."""
    with db.cursor() as cur:
        cur.execute(
            "UPDATE blocks SET source_text = %s WHERE id = %s",
            (text, block_id),
        )
    db.commit()


# =============================================================================
# Entity labels
# =============================================================================

def add_entity_label(db, entity_id: str, language: str, base_form: str) -> None:
    """Add or update a label for an entity (one per language)."""
    label_id = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entity_labels (id, entity_id, language, base_form)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (entity_id, language)
            DO UPDATE SET base_form = EXCLUDED.base_form
            """,
            (label_id, entity_id, language, base_form),
        )
    db.commit()


def delete_entity_label(db, entity_id: str, language: str) -> bool:
    """Delete a label by entity and language. Returns True if deleted."""
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM entity_labels WHERE entity_id = %s AND language = %s",
            (entity_id, language),
        )
        deleted = cur.rowcount > 0
    db.commit()
    return deleted


# =============================================================================
# Entity properties
# =============================================================================

def set_entity_property(db, entity_id: str, key: str, value: str) -> None:
    """Set one property on an entity, merged into the existing JSONB.

    Merged in the database rather than read-modify-written in Python: the
    old round trip was unlocked and silently dropped any key a concurrent
    CLI write had added in between.
    """
    with db.cursor() as cur:
        cur.execute(
            "UPDATE entities SET properties = "
            "COALESCE(properties, '{}'::jsonb) || %s::jsonb WHERE id = %s",
            (json.dumps({key: value}), entity_id),
        )
    db.commit()


def delete_entity_property(db, entity_id: str, key: str) -> bool:
    """Delete one property from an entity. Returns True if deleted.

    Same reasoning as :func:`set_entity_property`: the key is removed in the
    database so that concurrent writes to other keys survive.
    """
    with db.cursor() as cur:
        cur.execute(
            "UPDATE entities SET properties = properties - %s "
            "WHERE id = %s AND properties ? %s",
            (key, entity_id, key),
        )
        deleted = cur.rowcount > 0
    db.commit()
    return deleted


# =============================================================================
# Mention deletion
# =============================================================================

def delete_mention(db, mention_id: str) -> None:
    """Delete a mention by its id."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM mentions WHERE id = %s", (mention_id,))
    db.commit()


# =============================================================================
# Alignment deletion
# =============================================================================

def create_alignment(db, source_block_id: str, target_block_id: str,
                     alignment_type: str = "translation") -> str | None:
    """Create a block alignment. Returns alignment id, or None if duplicate."""
    alignment_id = str(uuid.uuid4())
    with db.cursor() as cur:
        # Same rule the CLI enforces: an alignment records one meaning in two
        # languages, so two blocks in one language are not an alignment.
        guards.ensure_blocks_alignable(cur, source_block_id, target_block_id)
        cur.execute(
            """SELECT 1 FROM block_alignments
               WHERE (source_block_id = %s AND target_block_id = %s)
                  OR (source_block_id = %s AND target_block_id = %s)""",
            (source_block_id, target_block_id, target_block_id, source_block_id),
        )
        if cur.fetchone():
            return None
        cur.execute(
            "INSERT INTO block_alignments (id, source_block_id, target_block_id, alignment_type) "
            "VALUES (%s, %s, %s, %s)",
            (alignment_id, source_block_id, target_block_id, alignment_type),
        )
    db.commit()
    return alignment_id


def delete_alignment(db, alignment_id: str) -> None:
    """Delete a block alignment by its id."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM block_alignments WHERE id = %s", (alignment_id,))
    db.commit()


# =============================================================================
# Import / Export (same functions as CLI and desktop sidecar)
# =============================================================================

def export_json_to_path(db, path: str) -> Path:
    """Export the work as JSON to path. Returns the resolved Path."""
    from littera.cli.io import export_work_json

    dest = Path(path).expanduser()
    data = export_work_json(db)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def export_markdown_to_path(db, path: str, compile: bool = False) -> Path:
    """Export the work as Markdown to path. Returns the resolved Path."""
    from littera.cli.io import export_work_markdown

    dest = Path(path).expanduser()
    dest.write_text(export_work_markdown(db, compile=compile), encoding="utf-8")
    return dest


def write_work_snapshot(db, work_dir, name: str | None = None) -> Path:
    """Write a timestamped JSON snapshot under .littera/snapshots/.

    Same writer the CLI's `littera snapshot` uses; the TUI is where cascading
    deletes and imports happen, so it must be reachable from here too.
    """
    from littera.cli.io import write_snapshot

    return write_snapshot(Path(work_dir), db, name)


def import_json_from_path(db, path: str) -> dict:
    """Import a work JSON file into the current work. Returns summary counts."""
    from littera.cli.io import import_work_json

    src = Path(path).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    return import_work_json(db, data)
