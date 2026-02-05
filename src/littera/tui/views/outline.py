from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class OutlineView(View):
    name = "outline"

    # Muted color for help text (Textual markup)
    HELP_STYLE = "[dim]"
    HELP_END = "[/dim]"

    def _build_breadcrumb(self, state: AppState) -> str:
        """Build breadcrumb path string like: Work > Doc > Section"""
        parts = ["Work"]
        for elem in state.path:
            parts.append(elem.title)
        return " > ".join(parts)

    def _get_hints(self, nav_level: str, has_selection: bool) -> str:
        """Get contextual hints for current navigation level."""
        base_hints = {
            "documents": "a:add doc  d:delete  Enter:drill  Esc:back  e:entities",
            "sections": "a:add sec  d:delete  Enter:drill  Esc:back  Ctrl+E:edit title",
            "blocks": "a:add blk  d:delete  Enter:edit  l:link entity  Esc:back",
        }
        return base_hints.get(nav_level, "a:add  d:delete  Enter:select  Esc:back")

    def _get_model_help(self, nav_level: str) -> str:
        """Get contextual help explaining the mental model."""
        h = self.HELP_STYLE
        e = self.HELP_END

        if nav_level == "documents":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document    ← you are here{e}
{h}       └─ Section{e}
{h}            └─ Block{e}

{h}Documents group sections together.{e}
{h}Each document is a standalone piece{e}
{h}— an article, essay, or chapter.{e}

{h}─────────────────────────{e}
{h}Enter  — drill into document{e}
{h}a      — add new document{e}
{h}e      — switch to Entities{e}
"""

        elif nav_level == "sections":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document{e}
{h}       └─ Section    ← you are here{e}
{h}            └─ Block{e}

{h}Sections divide a document.{e}
{h}Each section is a logical part{e}
{h}— a subchapter, scene, or argument.{e}

{h}─────────────────────────{e}
{h}Enter  — drill into section{e}
{h}Ctrl+E — edit title{e}
{h}Esc    — back to documents{e}
"""

        elif nav_level == "blocks":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document{e}
{h}       └─ Section{e}
{h}            └─ Block    ← you are here{e}

{h}Blocks are text fragments.{e}
{h}Each block has a language (en/pl/...){e}
{h}and can be linked to an Entity.{e}

{h}─────────────────────────{e}
{h}Enter  — edit block text{e}
{h}l      — link to Entity{e}
{h}Esc    — back to sections{e}
"""

        return ""

    def render(self, state: AppState):
        items: list[ListItem] = []
        detail = ""

        cur = state.db.cursor()

        nav_level = state.nav_level
        model_help = self._get_model_help(nav_level)

        # Determine what to list based on path depth
        if not state.path:
            # Show documents
            cur.execute("SELECT id, title FROM documents ORDER BY created_at")
            rows = cur.fetchall()
            if not rows:
                detail = f"No documents yet.\nPress 'a' to add one.\n{model_help}"
            else:
                for doc_id, title in rows:
                    # Textual widget ids can't start with a number; prefix the UUID.
                    items.append(ListItem(Static(f"DOC  {title}"), id=f"doc-{doc_id}"))
                detail = model_help
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
                    detail = f"No sections in '{last.title}' yet.\nPress 'a' to add one.\n{model_help}"
                else:
                    for sec_id, title in rows:
                        items.append(
                            ListItem(Static(f"SEC  {title}"), id=f"sec-{sec_id}")
                        )
                    detail = model_help
            elif last.kind == "section":
                # Show blocks
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (last.id,),
                )
                rows = cur.fetchall()
                if not rows:
                    detail = f"No blocks in '{last.title}' yet.\nPress 'a' to add one.\n{model_help}"
                else:
                    for block_id, lang, text in rows:
                        preview = text.replace("\n", " ")[:60]
                        items.append(
                            ListItem(
                                Static(f"BLK  ({lang}) {preview}"), id=f"blk-{block_id}"
                            )
                        )
                    detail = model_help

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

        breadcrumb = self._build_breadcrumb(state)
        hints = self._get_hints(state.nav_level, bool(state.entity_selection.id))

        return [
            Vertical(
                Static(breadcrumb, id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav"),
                    Static(detail, id="detail"),
                    id="outline-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
