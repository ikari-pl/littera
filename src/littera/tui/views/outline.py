from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class OutlineView(View):
    name = "outline"

    def render(self, state: AppState):
        items: list[ListItem] = []
        detail = "Select an item (Enter: drill down, a: add, Ctrl+E: edit title, d: delete, Esc: back)"

        cur = state.db.cursor()

        # Determine what to list based on path depth
        if not state.path:
            # Show documents
            cur.execute("SELECT id, title FROM documents ORDER BY created_at")
            rows = cur.fetchall()
            if not rows:
                detail = "No documents yet.\nPress 'a' to add a document."
            else:
                for doc_id, title in rows:
                    # Textual widget ids can't start with a number; prefix the UUID.
                    items.append(ListItem(Static(f"DOC  {title}"), id=f"doc-{doc_id}"))
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
                    detail = f"No sections in {last.title} yet.\n\nPress 'a' to add a section."
                else:
                    for sec_id, title in rows:
                        items.append(
                            ListItem(Static(f"SEC  {title}"), id=f"sec-{sec_id}")
                        )
                    detail = f"Sections in {last.title}\na: add section  Ctrl+E: edit title  d: delete"
            elif last.kind == "section":
                # Show blocks
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (last.id,),
                )
                rows = cur.fetchall()
                if not rows:
                    detail = (
                        f"No blocks in {last.title} yet.\n\nPress 'a' to add a block."
                    )
                else:
                    for block_id, lang, text in rows:
                        preview = text.replace("\n", " ")[:60]
                        items.append(
                            ListItem(
                                Static(f"BLK  ({lang}) {preview}"), id=f"blk-{block_id}"
                            )
                        )
                    detail = f"Blocks in {last.title}\na: add block  d: delete  Enter: edit  l: link"

        sel = state.entity_selection
        if sel and sel.id:
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
                detail = (
                    f"Document: {title}\nSections: {sec_count}\n\nEnter: drill down"
                )
            elif sel.kind == "section":
                cur.execute("SELECT title FROM sections WHERE id = %s", (raw_id,))
                row = cur.fetchone()
                title = row[0] if row else raw_id
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
                    detail = f"Block ({lang})\n\n{text}\n\nEnter: edit  l: link"
                else:
                    detail = f"Block: {raw_id}"

        return [
            Horizontal(
                ListView(*items, id="nav"),
                Static(detail, id="detail"),
                id="outline-layout",
            )
        ]
