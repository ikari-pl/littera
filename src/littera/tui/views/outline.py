from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static
from littera.tui.state import AppState
from littera.tui.views.base import View


class OutlineView(View):
    name = "outline"

    def render(self, state: AppState):
        items = []
        detail = "Select an item (Enter: drill down, a: add, Ctrl+E: edit title, d: delete, Esc: back)"

        cur = state.db.cursor()

        # Determine what to list based on path depth
        if not state.path:
            # Show documents
            cur.execute("SELECT id, title FROM documents ORDER BY created_at")
            rows = cur.fetchall()
            if not rows:
                items = []
                detail = "No documents yet.\nPress 'a' to add a document."
            else:
                for doc_id, title in rows:
                    items.append(ListItem(Static(f"DOC  {title}"), id=f"doc_{doc_id}"))
                detail = "Documents\na: add document  Ctrl+E: edit title  d: delete"
        else:
            last = state.path[-1]
            if last.kind == "document":
                # Show sections
                cur.execute(
                    "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                    (last.id,),
                )
                rows = cur.fetchall()
                if not rows:
                    items = []
                    detail = "No sections in {last.title} yet.\n\nPress 'a' to add a section."
                else:
                    for sec_id, title in rows:
                        items.append(
                            ListItem(Static(f"SEC  {title}"), id=f"sec_{sec_id}")
                        )
                    detail = "Sections in {last.title}\na: add section  Ctrl+E: edit title  d: delete"
            elif last.kind == "section":
                # Show blocks
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (last.id,),
                )
                rows = cur.fetchall()
                if not rows:
                    items = []
                    detail = (
                        "No blocks in {last.title} yet.\n\nPress 'a' to add a block."
                    )
                else:
                    for block_id, lang, text in rows:
                        preview = text.replace("\n", " ")[:60]
                        items.append(
                            ListItem(
                                Static(f"BLK  ({lang}) {preview}"), id=f"blk_{block_id}"
                            )
                        )
                    detail = (
                        f"Blocks in {last.title}\na: add block  d: delete  Enter: edit"
                    )

        # Show selection details if any
        sel = state.entity_selection
        if sel and sel.id:
            cur = state.db.cursor()
            raw_id = sel.id.split("_", 1)[1] if "_" in sel.id else sel.id

            if sel.kind == "document":
                cur.execute("SELECT title FROM documents WHERE id = %s", (raw_id,))
                row = cur.fetchone()
                title = row[0] if row else sel.id
                cur.execute(
                    "SELECT COUNT(*) FROM sections WHERE document_id = %s",
                    (raw_id,),
                )
                sec_count = cur.fetchone()[0]
                detail = (
                    f"Document: {title}\nSections: {sec_count}\n\nEnter: drill down"
                )
            elif sel.kind == "section":
                cur.execute("SELECT title FROM sections WHERE id = %s", (raw_id,))
                row = cur.fetchone()
                title = row[0] if row else sel.id
                cur.execute(
                    "SELECT COUNT(*) FROM blocks WHERE section_id = %s",
                    (raw_id,),
                )
                block_count = cur.fetchone()[0]
                detail = f"Section: {title}\nBlocks: {block_count}\n\nEnter: drill down"
            elif sel.kind == "block":
                cur.execute(
                    "SELECT language, source_text FROM blocks WHERE id = %s",
                    (raw_id,),
                )
                row = cur.fetchone()
                if row:
                    lang, text = row
                    detail = f"Block ({lang})\n\n{text}\n\nEnter: edit"
                else:
                    detail = f"Block: {sel.id}"

        return [
            Horizontal(
                ListView(*items, id="nav"),
                Static(detail, id="detail"),
                id="outline-layout",
            )
        ]
