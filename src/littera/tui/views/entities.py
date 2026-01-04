from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class EntitiesView(View):
    name = "entities"

    def render(self, state: AppState):
        items = []
        detail = "Select an entity"

        cur = state.db.cursor()
        cur.execute(
            "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
        )
        rows = cur.fetchall()
        for entity_id, entity_type, name in rows:
            label = name or "(unnamed)"
            items.append(ListItem(Static(f"{entity_type}: {label}"), id=str(entity_id)))

        if state.selection.kind == "entity" and state.selection.id:
            entity_id = state.selection.id
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
                SELECT language, base_form
                FROM entity_labels
                WHERE entity_id = %s
                ORDER BY language
                """,
                (entity_id,),
            )
            labels = cur.fetchall()

            cur.execute(
                """
                SELECT d.title, s.title, b.language, b.source_text
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

            detail_lines = [f"Entity: {entity_type} {name}", ""]

            if labels:
                detail_lines.append("Labels:")
                for lang, base_form in labels:
                    detail_lines.append(f"  - {lang}: {base_form}")
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
