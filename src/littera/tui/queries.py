"""View-layer data fetching (DB reads only).

All database reads needed to populate view state live here.
Views become pure functions of state — no DB access in render().

Usage in app.py:
    queries.refresh_outline(state)   # before OutlineView.render()
    queries.refresh_entities(state)  # before EntitiesView.render()
"""

from littera.cli.block import SIBLING_ORDER_SQL
from littera.cli.words import count_scope
from littera.tui.state import (
    AlignmentItem,
    AppState,
    EntityItem,
    OutlineItem,
    ReviewItem,
)

# =============================================================================
# Outline
# =============================================================================

UNTITLED = "(untitled)"


def display_title(title: str | None) -> str:
    """How a document or section title reads on screen.

    NULL is a real title, not an error: a scene break in a manuscript has no
    heading. It is shown as "(untitled)" and never stored that way.
    """
    return title if title and title.strip() else UNTITLED


def refresh_outline(state: AppState) -> None:
    """Populate state.outline.items and state.outline.detail from DB."""
    items: list[OutlineItem] = []
    detail = ""

    with state.db.cursor() as cur:
        if not state.path:
            # Documents level
            cur.execute(f"SELECT id, title FROM documents ORDER BY {SIBLING_ORDER_SQL}")
            for doc_id, title in cur.fetchall():
                items.append(OutlineItem(id=str(doc_id), kind="document", title=title))
        else:
            last = state.path[-1]
            if last.kind == "document":
                cur.execute(
                    f"SELECT id, title FROM sections WHERE document_id = %s ORDER BY {SIBLING_ORDER_SQL}",
                    (last.id,),
                )
                for sec_id, title in cur.fetchall():
                    items.append(OutlineItem(id=str(sec_id), kind="section", title=title))
            elif last.kind == "section":
                cur.execute(
                    f"SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY {SIBLING_ORDER_SQL}",
                    (last.id,),
                )
                for block_id, lang, text in cur.fetchall():
                    preview = (text or "").replace("\n", " ").strip()[:60]
                    # An empty block is a real, addressable block; it just has
                    # nothing in it yet. Say so rather than showing a blank row.
                    preview = preview or "(empty)"
                    items.append(
                        OutlineItem(id=str(block_id), kind="block", title=preview, language=lang)
                    )

        # Detail for selected item
        sel = state.entity_selection
        if sel and sel.id:
            detail = _outline_detail(cur, sel, state.db)

    state.outline.items = items
    # An explicit override (e.g. "show mentions") wins over the
    # selection-derived detail until the reducer clears it.
    if state.outline.detail_override is not None:
        detail = state.outline.detail_override
    state.outline.detail = detail


def _outline_detail(cur, sel, conn) -> str:
    """Build detail string for the selected outline item."""
    raw_id = sel.id

    if sel.kind == "document":
        cur.execute("SELECT title FROM documents WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        title = display_title(row[0]) if row else raw_id
        cur.execute(
            "SELECT COUNT(*) FROM sections WHERE document_id = %s",
            (raw_id,),
        )
        sec_count = cur.fetchone()[0]
        words = count_scope(conn, document_id=raw_id)["words"]
        return (
            f"Document: {title}\nSections: {sec_count}\nWords: {words}\n\n"
            "Enter: drill down"
        )

    elif sel.kind == "section":
        cur.execute("SELECT title FROM sections WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        title = display_title(row[0]) if row else raw_id
        cur.execute(
            "SELECT COUNT(*) FROM blocks WHERE section_id = %s",
            (raw_id,),
        )
        block_count = cur.fetchone()[0]
        words = count_scope(conn, section_id=raw_id)["words"]
        return (
            f"Section: {title}\nBlocks: {block_count}\nWords: {words}\n\n"
            "Enter: drill down"
        )

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

EMPTY_ENTITIES = (
    "No entities yet.\n\n"
    "Entities are the global concepts, people and places your writing is\n"
    "about. Press 'a' to add one, then 'l' on a block to mention it."
)

EMPTY_ALIGNMENTS = (
    "No alignments yet.\n\n"
    "An alignment links two blocks — a paragraph and its translation,\n"
    "say. Press 'a' to pick the two blocks."
)

EMPTY_REVIEWS = (
    "No reviews yet.\n\n"
    "A review is a scoped note about quality or intent: what to fix, and\n"
    "where. Press 'a' to write one."
)


def refresh_entities(state: AppState) -> None:
    """Populate state.entities.items and state.entities.detail from DB."""
    items: list[EntityItem] = []
    detail = "Select an entity — Enter edits its note, L labels, p properties"

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

    if not items:
        detail = EMPTY_ENTITIES
    state.entities.items = items
    # An explicit override (e.g. "show mentions") wins over the
    # selection-derived detail until the reducer clears it.
    if state.entities.detail_override is not None:
        detail = state.entities.detail_override
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
                f"  - {display_title(doc_title)} / {display_title(sec_title)} ({lang}) {preview}"
            )
    else:
        detail_lines.append("Mentions:")
        detail_lines.append("  (none)")

    return "\n".join(detail_lines)


# =============================================================================
# Reviews
# =============================================================================

def refresh_reviews(state: AppState) -> None:
    """Populate state.reviews.items and detail from DB."""
    items: list[ReviewItem] = []
    work_id = state.work.get("work", {}).get("id") if state.work else None

    with state.db.cursor() as cur:
        cur.execute("""
            SELECT id, scope, scope_id, issue_type, description, severity
            FROM reviews
            WHERE work_id = %s
            ORDER BY created_at
        """, (work_id,))
        for rid, scope, scope_id, issue_type, desc, severity in cur.fetchall():
            preview = (desc or "").replace("\n", " ")[:60]
            items.append(ReviewItem(
                id=str(rid),
                severity=severity or "medium",
                scope=scope or "",
                issue_type=issue_type or "",
                description=preview,
            ))

        # Detail for selected review
        sel = state.reviews.selection
        detail = "Select a review — Enter or Ctrl+E edits it, d deletes it"
        if sel and sel.kind == "review" and sel.id:
            detail = _review_detail(cur, sel.id)

    if not items:
        detail = EMPTY_REVIEWS
    state.reviews.items = items
    # An explicit override (e.g. "show mentions") wins over the
    # selection-derived detail until the reducer clears it.
    if state.reviews.detail_override is not None:
        detail = state.reviews.detail_override
    state.reviews.detail = detail


def scope_target_label(cur, scope: str | None, scope_id) -> str | None:
    """Human name of a review's scope target, or None if it cannot be named.

    reviews.scope_id has no foreign key, so a target can legitimately be gone;
    say so rather than printing a bare UUID at the writer.
    """
    if not scope or not scope_id:
        return None
    scope_id = str(scope_id)

    sql_by_scope = {
        "work": "SELECT title FROM works WHERE id = %s",
        "document": "SELECT title FROM documents WHERE id = %s",
        "section": "SELECT title FROM sections WHERE id = %s",
        "entity": "SELECT canonical_label FROM entities WHERE id = %s",
        "block": "SELECT source_text FROM blocks WHERE id = %s",
    }
    sql = sql_by_scope.get(scope)
    if sql is None:
        return None

    cur.execute(sql, (scope_id,))
    row = cur.fetchone()
    if row is None:
        return "(deleted)"
    value = (row[0] or "").replace("\n", " ").strip()
    if not value:
        return UNTITLED
    return value[:60] + ("…" if len(value) > 60 else "")


def fetch_scope_label(db, scope: str | None, scope_id) -> str | None:
    """Name of a review scope target, for dialogs. None if it has no name."""
    with db.cursor() as cur:
        return scope_target_label(cur, scope, scope_id)


def _review_detail(cur, review_id: str) -> str:
    """Build detail string for a selected review."""
    cur.execute(
        """
        SELECT id, scope, scope_id, issue_type, description, severity,
               metadata, created_at
        FROM reviews
        WHERE id = %s
        """,
        (review_id,),
    )
    row = cur.fetchone()
    if row is None:
        return f"Review {review_id} not found"

    _rid, scope, scope_id, issue_type, description, severity, metadata, created_at = row

    # The id says nothing to a writer; the severity and the first line of the
    # description say what this review is.
    headline = (description or "(no description)").strip().splitlines()[0]
    lines = [f"Review [{severity or 'medium'}]: {headline}", ""]
    if scope:
        target = scope_target_label(cur, scope, scope_id)
        if target is not None:
            lines.append(f"Scope: {scope} — {target}")
        elif scope_id:
            # A scope with no readable target (e.g. alignment): the id is all
            # there is, and dropping it would hide the binding entirely.
            lines.append(f"Scope: {scope} ({scope_id})")
        else:
            lines.append(f"Scope: {scope}")
    if issue_type:
        lines.append(f"Issue type: {issue_type}")
    lines.append(f"Created: {created_at}")
    lines.append("")
    lines.append("Description:")
    lines.append(description or "(empty)")

    if metadata:
        lines.append("")
        lines.append("Metadata:")
        for key, value in metadata.items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


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


def fetch_review(db, review_id: str) -> tuple[str, str]:
    """Return (description, severity) for a review."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT description, severity FROM reviews WHERE id = %s",
            (review_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"Review {review_id} not found")
    return row[0] or "", row[1] or "medium"


def fetch_block_mentions(db, block_id: str) -> list[tuple[str, str, str, str, str | None]]:
    """Return list of (mention_id, entity_type, entity_label, language, surface_form) for a block."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, e.entity_type, e.canonical_label, m.language, m.surface_form
            FROM mentions m
            JOIN entities e ON e.id = m.entity_id
            WHERE m.block_id = %s
            ORDER BY e.canonical_label
            """,
            (block_id,),
        )
        return [
            (str(r[0]), r[1], r[2] or "(unnamed)", r[3], r[4])
            for r in cur.fetchall()
        ]


def fetch_entity_labels(db, entity_id: str) -> list[tuple[str, str]]:
    """(language, base_form) for every label on an entity."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT language, base_form FROM entity_labels "
            "WHERE entity_id = %s ORDER BY language",
            (entity_id,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def fetch_entity_properties(db, entity_id: str) -> dict:
    """The entity's properties object, or an empty dict."""
    with db.cursor() as cur:
        cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
        row = cur.fetchone()
    if not row or not row[0]:
        return {}
    return dict(row[0])


def list_entity_types(db) -> list[str]:
    """Entity types already used in this database, most common first."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT entity_type, COUNT(*) AS n FROM entities "
            "GROUP BY entity_type ORDER BY n DESC, entity_type"
        )
        types = [row[0] for row in cur.fetchall() if row[0]]
    for default in ("concept", "person", "place"):
        if default not in types:
            types.append(default)
    return types


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


# =============================================================================
# Alignments
# =============================================================================

def list_blocks_for_picker(db) -> list[tuple[str, str]]:
    """Return [(block_id, label), ...] for alignment pickers."""
    from littera.cli.block import GLOBAL_BLOCK_ORDER_SQL

    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT b.id, b.language, b.source_text, d.title, s.title
            FROM blocks b
            JOIN sections s ON s.id = b.section_id
            JOIN documents d ON d.id = s.document_id
            ORDER BY {GLOBAL_BLOCK_ORDER_SQL}
            """
        )
        rows = cur.fetchall()
    options: list[tuple[str, str]] = []
    for bid, lang, text, doc_title, sec_title in rows:
        preview = (text or "").replace("\n", " ")[:50] or "(empty)"
        label = f"{doc_title or '?'} › {sec_title or '?'}: [{lang}] {preview}"
        options.append((str(bid), label))
    return options


def refresh_alignments(state: AppState) -> None:
    """Populate state.alignments.items from DB."""
    items: list[AlignmentItem] = []
    detail = "Select an alignment — d deletes it, g looks for gaps"

    with state.db.cursor() as cur:
        cur.execute("""
            SELECT a.id, sb.language, sb.source_text,
                   tb.language, tb.source_text, a.alignment_type
            FROM block_alignments a
            JOIN blocks sb ON sb.id = a.source_block_id
            JOIN blocks tb ON tb.id = a.target_block_id
            ORDER BY a.created_at
        """)
        for aid, sl, st, tl, tt, atype in cur.fetchall():
            items.append(AlignmentItem(
                id=str(aid),
                source_lang=sl,
                source_preview=st.replace("\n", " ")[:40],
                target_lang=tl,
                target_preview=tt.replace("\n", " ")[:40],
                alignment_type=atype or "translation",
            ))

        # Detail for selected alignment
        sel = state.alignments.selection
        if sel and sel.kind == "alignment" and sel.id:
            detail = _alignment_detail(cur, sel.id)

    if not items:
        detail = EMPTY_ALIGNMENTS
    state.alignments.items = items
    # An explicit override (e.g. "show mentions") wins over the
    # selection-derived detail until the reducer clears it.
    if state.alignments.detail_override is not None:
        detail = state.alignments.detail_override
    state.alignments.detail = detail


def _alignment_detail(cur, alignment_id: str) -> str:
    """Build detail string for a selected alignment."""
    cur.execute(
        """
        SELECT a.alignment_type, a.confidence,
               sb.language, sb.source_text,
               tb.language, tb.source_text
        FROM block_alignments a
        JOIN blocks sb ON sb.id = a.source_block_id
        JOIN blocks tb ON tb.id = a.target_block_id
        WHERE a.id = %s
        """,
        (alignment_id,),
    )
    row = cur.fetchone()
    if not row:
        return f"Alignment: {alignment_id}"

    atype, confidence, src_lang, src_text, tgt_lang, tgt_text = row

    lines = [
        f"Type: {atype or 'translation'}",
    ]
    if confidence is not None:
        lines.append(f"Confidence: {confidence}")
    lines.append("")
    lines.append(f"Source ({src_lang}):")
    lines.append(src_text[:200])
    lines.append("")
    lines.append(f"Target ({tgt_lang}):")
    lines.append(tgt_text[:200])
    lines.append("")
    lines.append("d: delete  g: show gaps")

    return "\n".join(lines)


def fetch_alignment_gaps(db) -> str:
    """Detect entities missing labels in aligned languages.

    Returns a formatted string describing the gaps found.
    """
    lines: list[str] = []
    total_gaps = 0
    no_gap_count = 0

    with db.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.source_block_id, a.target_block_id,
                   sb.language, sb.source_text,
                   tb.language, tb.source_text
            FROM block_alignments a
            JOIN blocks sb ON sb.id = a.source_block_id
            JOIN blocks tb ON tb.id = a.target_block_id
            ORDER BY a.created_at
        """)
        alignments = cur.fetchall()

        if not alignments:
            return "No alignments to check."

        for _, src_block_id, tgt_block_id, src_lang, src_text, tgt_lang, tgt_text in alignments:
            direction_gaps: list[tuple[str, str, str, str]] = []
            for from_block_id, from_lang, to_lang in [
                (src_block_id, src_lang, tgt_lang),
                (tgt_block_id, tgt_lang, src_lang),
            ]:
                cur.execute(
                    """
                    SELECT DISTINCT e.id, e.entity_type, e.canonical_label
                    FROM mentions m
                    JOIN entities e ON e.id = m.entity_id
                    WHERE m.block_id = %s
                    """,
                    (from_block_id,),
                )
                entities = cur.fetchall()

                for eid, etype, canonical in entities:
                    cur.execute(
                        "SELECT 1 FROM entity_labels WHERE entity_id = %s AND language = %s",
                        (eid, to_lang),
                    )
                    if not cur.fetchone():
                        direction_gaps.append((etype, canonical, from_lang, to_lang))

            if not direction_gaps:
                no_gap_count += 1
                continue

            # Deduplicate
            seen: set[tuple[str, str]] = set()
            unique_gaps: list[tuple[str, str, str, str]] = []
            for etype, canonical, from_lang, to_lang in direction_gaps:
                key = (canonical, to_lang)
                if key not in seen:
                    seen.add(key)
                    unique_gaps.append((etype, canonical, from_lang, to_lang))

            src_preview = src_text.replace("\n", " ")[:40]
            tgt_preview = tgt_text.replace("\n", " ")[:40]
            lines.append(
                f'({src_lang}) "{src_preview}" '
                f'<-> ({tgt_lang}) "{tgt_preview}":'
            )
            for etype, canonical, from_lang, to_lang in unique_gaps:
                total_gaps += 1
                lines.append(f'  {etype} "{canonical}" -- no label for {to_lang}')
            lines.append("")

    if no_gap_count:
        lines.append(f"No gaps for {no_gap_count} other alignment(s).")
    if total_gaps == 0:
        lines.append("No gaps found.")
    else:
        lines.append(f"Total gaps: {total_gaps}")

    return "\n".join(lines)
