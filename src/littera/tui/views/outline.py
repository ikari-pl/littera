from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class OutlineView(View):
    name = "outline"

    def render(self, state: AppState):
        items = []
        detail = "Select an item"

        cur = state.db.cursor()

        if state.nav_level == "documents":
            cur.execute("SELECT id, title FROM documents ORDER BY created_at")
            rows = cur.fetchall()
            for doc_id, title in rows:
                items.append(ListItem(Static(f"DOC  {title}"), id=str(doc_id)))
        elif state.nav_level == "sections":
            cur.execute(
                "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                (state.document_id,),
            )
            rows = cur.fetchall()
            for sec_id, title in rows:
                items.append(ListItem(Static(f"SEC  {title}"), id=str(sec_id)))
        else:
            cur.execute(
                "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                (state.section_id,),
            )
            rows = cur.fetchall()
            for block_id, lang, text in rows:
                preview = text.replace("\n", " ")[:60]
                items.append(
                    ListItem(Static(f"BLK  ({lang}) {preview}"), id=str(block_id))
                )

        if state.selection.id and state.selection.kind:
            if state.selection.kind == "document":
                cur.execute(
                    "SELECT title FROM documents WHERE id = %s",
                    (state.selection.id,),
                )
                row = cur.fetchone()
                title = row[0] if row else state.selection.id
                cur.execute(
                    "SELECT COUNT(*) FROM sections WHERE document_id = %s",
                    (state.selection.id,),
                )
                sec_count = cur.fetchone()[0]
                detail = f"Document: {title}\nSections: {sec_count}\n\nEnter: drill down  Esc: back"
            elif state.selection.kind == "section":
                cur.execute(
                    "SELECT title FROM sections WHERE id = %s",
                    (state.selection.id,),
                )
                row = cur.fetchone()
                title = row[0] if row else state.selection.id
                cur.execute(
                    "SELECT COUNT(*) FROM blocks WHERE section_id = %s",
                    (state.selection.id,),
                )
                block_count = cur.fetchone()[0]
                detail = f"Section: {title}\nBlocks: {block_count}\n\nEnter: drill down  Esc: back"
            else:
                cur.execute(
                    "SELECT language, source_text FROM blocks WHERE id = %s",
                    (state.selection.id,),
                )
                row = cur.fetchone()
                if row:
                    lang, text = row
                    detail = f"Block ({lang})\n\n{text}\n\nEnter: edit   Esc: back"
                else:
                    detail = f"Block: {state.selection.id}"

        return [
            Horizontal(
                ListView(*items, id="nav"),
                Static(detail, id="detail"),
                id="outline-layout",
            )
        ]
