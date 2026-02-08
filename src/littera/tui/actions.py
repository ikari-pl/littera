"""DB mutation functions for TUI actions.

All database writes live here. App.py action methods become thin
orchestrators: guard → call actions.py → dispatch state → render.
"""

import json
import uuid


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


def create_block(db, section_id: str) -> str:
    """Create a new block in a section. Returns the new block id."""
    block_id = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO blocks (id, section_id, block_type, language, source_text) "
            "VALUES (%s, %s, 'paragraph', 'en', '(new block)')",
            (block_id, section_id),
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
                  scope: str | None = None, issue_type: str | None = None) -> str:
    """Create a new review. Returns the review id."""
    review_id = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO reviews (id, work_id, description, severity, scope, issue_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (review_id, work_id, description, severity, scope, issue_type))
    db.commit()
    return review_id


def delete_review(db, review_id: str) -> None:
    """Delete a review by its id."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    db.commit()


def delete_item(db, kind: str, item_id: str) -> None:
    """Delete a document, section, or block by kind and id."""
    with db.cursor() as cur:
        if kind == "document":
            cur.execute("DELETE FROM documents WHERE id = %s", (item_id,))
        elif kind == "section":
            cur.execute("DELETE FROM sections WHERE id = %s", (item_id,))
        elif kind == "block":
            cur.execute("DELETE FROM blocks WHERE id = %s", (item_id,))
        else:
            return
    db.commit()


def delete_entity(db, entity_id: str) -> None:
    """Delete an entity by id. Cascades to mentions and labels via FK."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
    db.commit()


# =============================================================================
# Reordering
# =============================================================================

def move_item(db, kind: str, item_id: str, new_position: int) -> bool:
    """Move a document or section to a new position (1-based).

    For documents: reorders among siblings in the same work.
    For sections: reorders among siblings in the same document.

    Returns True if the move was applied, False if position is out of range.
    """
    with db.cursor() as cur:
        if kind == "document":
            # Get siblings: all documents in the same work
            cur.execute(
                "SELECT id FROM documents "
                "WHERE work_id = (SELECT work_id FROM documents WHERE id = %s) "
                "ORDER BY order_index NULLS LAST, created_at",
                (item_id,),
            )
        elif kind == "section":
            # Get siblings: all sections in the same document
            cur.execute(
                "SELECT id FROM sections "
                "WHERE document_id = (SELECT document_id FROM sections WHERE id = %s) "
                "ORDER BY order_index NULLS LAST, created_at",
                (item_id,),
            )
        else:
            return False

        ids = [str(r[0]) for r in cur.fetchall()]

        if new_position < 1 or new_position > len(ids):
            return False

        # Remove target, insert at new position
        ids.remove(str(item_id))
        ids.insert(new_position - 1, str(item_id))

        # Bulk update order_index
        table = "documents" if kind == "document" else "sections"
        for idx, row_id in enumerate(ids, 1):
            cur.execute(
                f"UPDATE {table} SET order_index = %s WHERE id = %s",
                (idx, row_id),
            )
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


# =============================================================================
# Entity linking
# =============================================================================

def link_entity(db, block_id: str, entity_name: str) -> tuple[str, bool]:
    """Link a block to an entity by name. Auto-creates entity if needed.

    Returns (entity_id, created_new).
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM entities WHERE canonical_label = %s", (entity_name,)
        )
        row = cur.fetchone()

        created_new = False
        if row:
            entity_id = str(row[0])
        else:
            cur.execute(
                "INSERT INTO entities (entity_type, canonical_label) VALUES ('concept', %s) RETURNING id",
                (entity_name,),
            )
            new_row = cur.fetchone()
            if new_row is None:
                raise RuntimeError(f"Failed to create entity '{entity_name}'")
            entity_id = str(new_row[0])
            created_new = True

        # Get block language (required by mentions schema)
        cur.execute("SELECT language FROM blocks WHERE id = %s", (block_id,))
        lang_row = cur.fetchone()
        if lang_row is None:
            raise LookupError(f"Block {block_id} not found")
        language = lang_row[0]

        # Insert mention if not already linked
        cur.execute(
            "SELECT 1 FROM mentions WHERE block_id = %s AND entity_id = %s AND language = %s",
            (block_id, entity_id, language),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO mentions (block_id, entity_id, language) VALUES (%s, %s, %s)",
                (block_id, entity_id, language),
            )
    db.commit()
    return entity_id, created_new


# =============================================================================
# Saving edits
# =============================================================================

def save_entity_note(db, entity_id: str, work_id: str, text: str) -> None:
    """Save (upsert) an entity's work-scoped note."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (entity_id, work_id)
            DO UPDATE SET metadata = EXCLUDED.metadata
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
    """Set a property on an entity (merged into existing properties JSONB)."""
    with db.cursor() as cur:
        cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
        row = cur.fetchone()
        props = row[0] if row and row[0] else {}
        props[key] = value
        cur.execute(
            "UPDATE entities SET properties = %s WHERE id = %s",
            (json.dumps(props), entity_id),
        )
    db.commit()


def delete_entity_property(db, entity_id: str, key: str) -> bool:
    """Delete a property from an entity. Returns True if deleted."""
    with db.cursor() as cur:
        cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
        row = cur.fetchone()
        props = row[0] if row and row[0] else {}
        if key not in props:
            return False
        del props[key]
        cur.execute(
            "UPDATE entities SET properties = %s WHERE id = %s",
            (json.dumps(props) if props else None, entity_id),
        )
    db.commit()
    return True


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
