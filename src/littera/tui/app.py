"""Littera TUI application with refactored state architecture.

- Clean path-based navigation (work -> document -> section -> block)
- Isolated edit_session for editing overlay
- Unified selection model
"""

from __future__ import annotations

from pathlib import Path

import yaml

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Footer, Header, ListView
from textual.containers import Horizontal

from littera.tui.state import (
    AppState,
    Selection,
    PathElement,
    EditTarget,
    EditSession,
    EditKind,
    ViewName,
    ModeName,
)

from littera.tui.views.entities import EntitiesView
from littera.tui.views.editor import EditorView
from littera.tui.views.outline import OutlineView

from littera.db.bootstrap import start_postgres
from littera.db.workdb import postgres_config_from_work
from littera.db.embedded_pg import EmbeddedPostgresManager


class LitteraApp(App):
    CSS_PATH = "tui.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "back", "Back"),
        ("o", "outline", "Outline"),
        ("e", "entities", "Entities"),
        ("n", "edit_note", "Edit Note"),
        ("enter", "enter", "Enter/Drill Down"),
        ("a", "add_item", "Add Item"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
        ("^p", "palette", "Command Palette"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state: AppState | None = None
        self.views = {}
        self._pg_cfg = None
        self._pg_started_here = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(id="main")
        yield Footer()

    def on_mount(self) -> None:
        cfg = self._load_cfg()

        import psycopg

        littera_dir = Path.cwd() / ".littera"
        EmbeddedPostgresManager(littera_dir).ensure()

        pg_cfg = postgres_config_from_work(littera_dir, cfg)
        self._pg_cfg = pg_cfg
        self._pg_started_here = start_postgres(pg_cfg)

        conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)

        self.state = AppState(work=cfg, db=conn)
        self.views = {
            "outline": OutlineView(),
            "entities": EntitiesView(),
            "editor": EditorView(),
        }
        self._render_view()

    def on_unmount(self) -> None:
        if self.state is not None:
            self.state.db.close()

        if (
            getattr(self, "_pg_started_here", False)
            and getattr(self, "_pg_cfg", None) is not None
        ):
            from littera.db.bootstrap import stop_postgres

            stop_postgres(self._pg_cfg)

    # =====================
    # View switching
    # =====================

    def action_outline(self) -> None:
        if self.state is None:
            return
        self.state.view = "outline"
        self.state.mode = "browse"
        self.state.edit_session = None
        self._clear_undo_redo()
        self._render_view()

    def action_entities(self) -> None:
        if self.state is None:
            return
        self.state.view = "entities"
        self.state.mode = "browse"
        self.state.entity_selection = Selection()
        self.state.edit_session = None
        self._clear_undo_redo()
        self._render_view()

    # =====================
    # Navigation
    # =====================

    def action_enter(self) -> None:
        """Drill down into selected item."""
        if self.state is None:
            return
        if self.state.view != "outline":
            return
        if not self.state.entity_selection.id:
            return

        sel = self.state.entity_selection
        cur = self.state.db.cursor()

        if sel.kind == "document":
            cur.execute("SELECT title FROM documents WHERE id = %s", (sel.id,))
            row = cur.fetchone()
            title = row[0] if row else "Untitled"
            self.state.path.append(PathElement(kind="document", id=sel.id, title=title))
            self.state.entity_selection = Selection()
            self._render_view()

        elif sel.kind == "section":
            cur.execute("SELECT title FROM sections WHERE id = %s", (sel.id,))
            row = cur.fetchone()
            title = row[0] if row else "Untitled"
            self.state.path.append(PathElement(kind="section", id=sel.id, title=title))
            self.state.entity_selection = Selection()
            self._render_view()

        elif sel.kind == "block":
            self.action_edit_block()

    def action_back(self) -> None:
        """Go back: pop path, cancel editor, or deselect entity."""
        if self.state is None:
            return

        if self.state.view == "editor":
            self._cancel_edit()
            return

        if self.state.view == "entities":
            if self.state.entity_selection.kind == "entity":
                self.state.entity_selection = Selection()
                self._render_view()
                return
            self.action_outline()
            return

        # Outline view: pop path
        if self.state.path:
            self.state.path.pop()
            self.state.entity_selection = Selection()
            self._render_view()

    # =====================
    # Creation
    # =====================

    def action_add_item(self) -> None:
        """Add document/section/block at current level."""
        if self.state is None:
            return
        if self.state.view != "outline":
            return

        import uuid

        cur = self.state.db.cursor()
        nav_level = self.state.nav_level

        if nav_level == "documents":
            title = f"Doc {uuid.uuid4().hex[:8]}"
            doc_id = str(uuid.uuid4())
            work_id = self.state.work["work"]["id"]
            cur.execute(
                "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
                (doc_id, work_id, title),
            )
            self.state.db.commit()
            self.state.entity_selection = Selection(kind="document", id=doc_id)
            self._render_view()

        elif nav_level == "sections":
            doc = self.state.current_document
            if not doc:
                return
            title = f"Sec {uuid.uuid4().hex[:8]}"
            section_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO sections (id, document_id, title, order_index) VALUES (%s, %s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1))",
                (section_id, doc.id, title, doc.id),
            )
            self.state.db.commit()
            self.state.entity_selection = Selection(kind="section", id=section_id)
            self._render_view()

        elif nav_level == "blocks":
            section = self.state.current_section
            if not section:
                return
            block_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO blocks (id, section_id, block_type, language, source_text) VALUES (%s, %s, 'paragraph', 'en', '(new block)')",
                (block_id, section.id),
            )
            self.state.db.commit()
            self.state.entity_selection = Selection(kind="block", id=block_id)
            self._render_view()

    # =====================
    # Editing
    # =====================

    def action_edit_note(self) -> None:
        """Edit entity note."""
        if self.state is None:
            return
        if self.state.view != "entities":
            return
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return

        cur = self.state.db.cursor()
        cur.execute(
            "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
            (sel.id,),
        )
        row = cur.fetchone()
        if row is None:
            return
        entity_type, name = row

        work_id = self.state.work["work"]["id"] if self.state.work else None
        note = ""
        if work_id is not None:
            cur.execute(
                """
                SELECT metadata->>'note'
                FROM entity_work_metadata
                WHERE entity_id = %s AND work_id = %s
                """,
                (sel.id, work_id),
            )
            note_row = cur.fetchone()
            note = note_row[0] if note_row and note_row[0] else ""

        self._start_edit(
            EditTarget(kind="entity_note", id=sel.id),
            f"Note: {entity_type} {name}",
            note,
        )

    def action_edit_block(self) -> None:
        """Edit block text."""
        if self.state is None:
            return
        if self.state.view != "outline":
            return
        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        cur = self.state.db.cursor()
        cur.execute(
            "SELECT language, source_text FROM blocks WHERE id = %s",
            (sel.id,),
        )
        row = cur.fetchone()
        if row is None:
            return
        lang, text = row

        self._start_edit(
            EditTarget(kind="block_text", id=sel.id),
            f"Block ({lang})",
            text,
        )

    def action_save(self) -> None:
        """Save current edit."""
        if self.state is None:
            return
        if self.state.view != "editor":
            return
        session = self.state.edit_session
        if session is None:
            return

        new_text = session.current_text

        if session.target.kind == "entity_note":
            work_id = self.state.work["work"]["id"] if self.state.work else None
            if work_id is None:
                return
            import json

            cur = self.state.db.cursor()
            cur.execute(
                """
                INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (entity_id, work_id)
                DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                (session.target.id, work_id, json.dumps({"note": new_text})),
            )
            self.state.db.commit()
            self.state.undo_redo.record(
                session.target,
                session.original_text,
                new_text,
            )
            self.state.view = "entities"
            self.state.edit_session = None
            self._render_view()

        elif session.target.kind == "block_text":
            cur = self.state.db.cursor()
            cur.execute(
                "UPDATE blocks SET source_text = %s WHERE id = %s",
                (new_text, session.target.id),
            )
            self.state.db.commit()
            self.state.undo_redo.record(
                session.target,
                session.original_text,
                new_text,
            )
            self.state.view = "outline"
            self.state.edit_session = None
            self._render_view()

    def action_undo(self) -> None:
        if self.state is None or self.state.view != "editor":
            return
        session = self.state.edit_session
        if session is None:
            return
        edit = self.state.undo_redo.pop_undo()
        if edit is None:
            return
        session.current_text = edit.new
        self._update_editor_widget(session.current_text)

    def action_redo(self) -> None:
        if self.state is None or self.state.view != "editor":
            return
        session = self.state.edit_session
        if session is None:
            return
        edit = self.state.undo_redo.pop_redo()
        if edit is None:
            return
        session.current_text = edit.new
        self._update_editor_widget(session.current_text)

    # =====================
    # Internal helpers
    # =====================

    def _start_edit(self, target: EditTarget, title: str, text: str) -> None:
        self.state.edit_session = EditSession(
            target=target,
            original_text=text,
            current_text=text,
        )
        self.state.view = "editor"
        self.state.mode = "edit"
        self._render_view()

    def _cancel_edit(self) -> None:
        if self.state is None:
            return
        session = self.state.edit_session
        if session is None:
            return

        if session.target.kind == "entity_note":
            self.state.view = "entities"
        else:
            self.state.view = "outline"

        self.state.mode = "browse"
        self.state.edit_session = None
        self._render_view()

    def _clear_undo_redo(self) -> None:
        if self.state is None:
            return
        self.state.undo_redo.clear()

    def _update_editor_widget(self, text: str) -> None:
        editor_widget = self.screen.query_one("#editor")
        if hasattr(editor_widget, "text"):
            editor_widget.text = text
        elif hasattr(editor_widget, "value"):
            editor_widget.value = text

    def _render_view(self) -> None:
        if self.state is None:
            return

        container = self.screen.query_one("#main")
        container.remove_children()

        view = self.views[self.state.view]
        for widget in view.render(self.state):
            container.mount(widget)

    def _load_cfg(self) -> dict:
        work_dir = Path.cwd()
        littera_dir = work_dir / ".littera"
        if not littera_dir.exists():
            raise RuntimeError("Not a Littera work")
        return yaml.safe_load((littera_dir / "config.yml").read_text())

    # =====================
    # Event handlers
    # =====================

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.state is None:
            return

        item_id = event.item.id
        if item_id is None:
            return

        if self.state.view == "entities":
            self.state.entity_selection = Selection(kind="entity", id=item_id)
            self._render_view()
            return

        if self.state.view == "outline":
            cur = self.state.db.cursor()

            # Determine kind from nav level
            nav_level = self.state.nav_level
            kind_map = {
                "documents": "document",
                "sections": "section",
                "blocks": "block",
            }
            kind = kind_map.get(nav_level, "document")

            self.state.entity_selection = Selection(kind=kind, id=item_id)
            self._render_view()

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.action_back()
        elif event.key == "^p":
            self.action_show_palette()

    def action_show_palette(self) -> None:
        if self.state is None:
            return
        self.app.bell()
        self.app.exit()


if __name__ == "__main__":
    LitteraApp().run()
