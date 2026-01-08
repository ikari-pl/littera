from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class EntitiesView(View):
    name = "entities"

    def render(self, state: AppState):
        items = []
        detail = "Select an entity (n: edit note, a: add, o: outline)"

        cur = state.db.cursor()
        cur.execute(
            "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
        )
        rows = cur.fetchall()
        for row in rows:
            # Handle different row structures robustly
            if not isinstance(row, (list, tuple)):
                continue  # Skip malformed rows

            if len(row) >= 3:
                entity_id, entity_type, name = row[0], row[1], row[2]
            elif len(row) == 2:
                entity_id, entity_type = row[0], row[1]
                name = "(unnamed)"  # Handle missing canonical_label
            else:
                continue  # Skip malformed rows
            label = name or "(unnamed)"
            # Textual widget ids can't start with a number; prefix the UUID.
            items.append(
                ListItem(Static(f"{entity_type}: {label}"), id=f"ent-{entity_id}")
            )

        sel = state.entity_selection
        if sel and sel.kind == "entity" and sel.id:
            entity_id = sel.id
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
            if state.work and "work" in state.work:
                work_id = state.work["work"].get("id")

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

            # Initialize detail lines for entity info
            detail_lines = [f"Entity: {entity_type} {name}", ""]

            if labels:
                detail_lines.append("Labels:")
                for lang, base_form, aliases in labels:
                    detail_lines.append(f"  - {lang}: {base_form}")
                    if aliases:  # Handle optional aliases
                        detail_lines.append(f"    aliases: {aliases}")
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

            detail_lines.append("")

            detail_lines.append("Note (work-scoped):")
            detail_lines.append(note if note else "(no note)")
            detail_lines.append("")

            if mentions:
                detail_lines.append("Mentions:")
                for doc_title, sec_title, lang, text in mentions:
                    preview = text.replace("\n", " ")[:60]
                    detail_lines.append(
                        f"  - {doc_title} / {sec_title} ({lang}) {preview}"
                    )
            else:
                detail_lines.append("Mentions:")
                detail_lines.append("  (none)")

            detail_lines.append("")
            detail_lines.append("n: edit note   o: outline")

            detail = "\n".join(detail_lines)

        return [
            Horizontal(
                ListView(*items, id="nav"),
                Static(detail, id="detail"),
                id="entities-layout",
            )
        ]
