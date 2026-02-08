"""View-layer data fetching (DB reads only).

All database reads needed to populate view state live here.
Views become pure functions of state — no DB access in render().

Usage in app.py:
    queries.refresh_outline(state)   # before OutlineView.render()
    queries.refresh_entities(state)  # before EntitiesView.render()
"""

from littera.tui.state import AppState, OutlineItem, EntityItem


# =============================================================================
# Outline
# =============================================================================

def refresh_outline(state: AppState) -> None:
    """Populate state.outline.items and state.outline.detail from DB."""
    items: list[OutlineItem] = []
    detail = ""

    nav_level = state.nav_level
    model_help = ""  # Views handle help text display

    with state.db.cursor() as cur:
        if not state.path:
            # Documents level
            cur.execute("SELECT id, title FROM documents ORDER BY created_at")
            for doc_id, title in cur.fetchall():
                items.append(OutlineItem(id=str(doc_id), kind="document", title=title))
        else:
            last = state.path[-1]
            if last.kind == "document":
                cur.execute(
                    "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                    (last.id,),
                )
                for sec_id, title in cur.fetchall():
                    items.append(OutlineItem(id=str(sec_id), kind="section", title=title))
            elif last.kind == "section":
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (last.id,),
                )
                for block_id, lang, text in cur.fetchall():
                    preview = text.replace("\n", " ")[:60]
                    items.append(
                        OutlineItem(id=str(block_id), kind="block", title=preview, language=lang)
                    )

        # Detail for selected item
        sel = state.entity_selection
        if sel and sel.id:
            detail = _outline_detail(cur, sel)

    state.outline.items = items
    state.outline.detail = detail


def _outline_detail(cur, sel) -> str:
    """Build detail string for the selected outline item."""
    raw_id = sel.id

    if sel.kind == "document":
        cur.execute("SELECT title FROM documents WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        title = row[0] if row else raw_id
        cur.execute(
            "SELECT COUNT(*) FROM sections WHERE document_id = %s",
            (raw_id,),
        )
        sec_count = cur.fetchone()[0]
        return f"Document: {title}\nSections: {sec_count}\n\nEnter: drill down"

    elif sel.kind == "section":
        cur.execute("SELECT title FROM sections WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        title = row[0] if row else raw_id
        cur.execute(
            "SELECT COUNT(*) FROM blocks WHERE section_id = %s",
            (raw_id,),
        )
        block_count = cur.fetchone()[0]
        return f"Section: {title}\nBlocks: {block_count}\n\nEnter: drill down"

    elif sel.kind == "block":
        cur.execute(
            "SELECT language, source_text FROM blocks WHERE id = %s",
            (raw_id,),
        )
        row = cur.fetchone()
        if row:
            lang, text = row
            cur.execute(
                "SELECT COUNT(*) FROM mentions WHERE block_id = %s",
                (raw_id,),
            )
            mention_count = cur.fetchone()[0]
            mention_info = f"  Mentions: {mention_count}" if mention_count > 0 else ""
            return f"Block ({lang}){mention_info}\n\n{text}\n\nEnter: edit  l: link  M: mentions"
        return f"Block: {raw_id}"

    return ""


# =============================================================================
# Entities
# =============================================================================

def refresh_entities(state: AppState) -> None:
    """Populate state.entities.items and state.entities.detail from DB."""
    items: list[EntityItem] = []
    detail = "Select an entity"

    with state.db.cursor() as cur:
        cur.execute(
            "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
        )
        for row in cur.fetchall():
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            entity_id, entity_type, name = row[0], row[1], row[2]
            label = name or "(unnamed)"
            items.append(EntityItem(id=str(entity_id), entity_type=entity_type, label=label))

        # Detail for selected entity
        sel = state.entity_selection
        if sel and sel.kind == "entity" and sel.id:
            detail = _entity_detail(cur, sel.id, state.work)

    state.entities.items = items
    state.entities.detail = detail


def _entity_detail(cur, entity_id: str, work: dict | None) -> str:
    """Build detail string for a selected entity."""
    cur.execute(
        "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
        (entity_id,),
    )
    row = cur.fetchone()
    if row:
        entity_type, name = row
    else:
        entity_type, name = "?", entity_id

    work_id = None
    if work and "work" in work:
        work_id = work["work"].get("id")

    note = None
    if work_id is not None:
        cur.execute(
            """
            SELECT metadata->>'note'
            FROM entity_work_metadata
            WHERE entity_id = %s AND work_id = %s
            """,
            (entity_id, work_id),
        )
        note_row = cur.fetchone()
        note = note_row[0] if note_row else None

    cur.execute(
        """
        SELECT language, base_form, aliases
        FROM entity_labels
        WHERE entity_id = %s
        ORDER BY language
        """,
        (entity_id,),
    )
    labels = cur.fetchall()

    cur.execute(
        """
        SELECT d.title, s.title, b.language, b.source_text, m.entity_id, m.block_id
        FROM mentions m
        JOIN blocks b ON b.id = m.block_id
        JOIN sections s ON s.id = b.section_id
        JOIN documents d ON d.id = s.document_id
        WHERE m.entity_id = %s
        ORDER BY b.created_at DESC
        LIMIT 10
        """,
        (entity_id,),
    )
    mentions = cur.fetchall()

    # Properties
    cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
    prop_row = cur.fetchone()
    properties = prop_row[0] if prop_row and prop_row[0] else {}

    detail_lines = [f"Entity: {entity_type} {name}", ""]

    if labels:
        detail_lines.append("Labels:")
        for lang, base_form, aliases in labels:
            detail_lines.append(f"  - {lang}: {base_form}")
            if aliases:
                detail_lines.append(f"    aliases: {aliases}")
        detail_lines.append("")

    if properties:
        detail_lines.append("Properties:")
        for key, value in properties.items():
            detail_lines.append(f"  {key}: {value}")
        detail_lines.append("")

    detail_lines.append("Note (work-scoped):")
    detail_lines.append(note if note else "(no note)")
    detail_lines.append("")

    if mentions:
        detail_lines.append("Mentions:")
        for (
            doc_title,
            sec_title,
            lang,
            text,
            mention_entity_id,
            mention_block_id,
        ) in mentions:
            preview = text.replace("\n", " ")[:60]
            detail_lines.append(
                f"  - {doc_title} / {sec_title} ({lang}) {preview}"
            )
    else:
        detail_lines.append("Mentions:")
        detail_lines.append("  (none)")

    return "\n".join(detail_lines)


# =============================================================================
# Single-row fetch helpers (used by app.py actions)
# =============================================================================

def fetch_entity_note(db, entity_id: str, work_id: str) -> tuple[str, str, str]:
    """Fetch entity info + note for editing. Returns (entity_type, name, note)."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
            (entity_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"Entity {entity_id} not found")
        entity_type, name = row

        note = ""
        if work_id is not None:
            cur.execute(
                """
                SELECT metadata->>'note'
                FROM entity_work_metadata
                WHERE entity_id = %s AND work_id = %s
                """,
                (entity_id, work_id),
            )
            note_row = cur.fetchone()
            note = note_row[0] if note_row and note_row[0] else ""

    return entity_type, name, note


def fetch_block_text(db, block_id: str) -> tuple[str, str]:
    """Fetch block language and source_text. Returns (language, text)."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT language, source_text FROM blocks WHERE id = %s",
            (block_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"Block {block_id} not found")
    return row[0], row[1]


def fetch_block_mentions(db, block_id: str) -> list[tuple[str, str, str, str]]:
    """Return list of (mention_id, entity_type, entity_label, language) for a block."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, e.entity_type, e.canonical_label, m.language
            FROM mentions m
            JOIN entities e ON e.id = m.entity_id
            WHERE m.block_id = %s
            ORDER BY e.canonical_label
            """,
            (block_id,),
        )
        return [
            (str(r[0]), r[1], r[2] or "(unnamed)", r[3])
            for r in cur.fetchall()
        ]


def fetch_item_title(db, kind: str, item_id: str) -> str:
    """Fetch title for a document or section. Returns title string."""
    with db.cursor() as cur:
        if kind == "document":
            cur.execute("SELECT title FROM documents WHERE id = %s", (item_id,))
        elif kind == "section":
            cur.execute("SELECT title FROM sections WHERE id = %s", (item_id,))
        else:
            return "Untitled"
        row = cur.fetchone()
    return row[0] if row else "Untitled"
