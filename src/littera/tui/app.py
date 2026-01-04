"""Littera TUI application with undo/redo and editing.

- Explicit mode switching
- Embedded Postgres auto-start/stop with lease
- Save/cancel prompts and hotkeys
- Unique widget IDs per view
"""

from __future__ import annotations

from pathlib import Path

import yaml

from textual.app import App, ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Footer, Header, ListView
from textual.containers import Horizontal

from littera.tui.state import AppState, Selection
from littera.tui.undo import EditTarget, EditKind
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
        ("enter", "edit_block", "Edit Block"),
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

    def action_outline(self) -> None:
        if self.state is None:
            return
        self.state.view = "outline"
        self.state.mode = "browse"
        self._clear_undo_redo_on_view_change()
        self._render_view()

    def action_entities(self) -> None:
        if self.state is None:
            return
        self.state.view = "entities"
        self.state.mode = "browse"
        self.state.selection = Selection()
        self._clear_undo_redo_on_view_change()
        self._render_view()

    def action_edit_note(self) -> None:
        if self.state is None:
            return
        if self.state.view != "entities":
            return
        if self.state.selection.kind != "entity" or not self.state.selection.id:
            return

        cur = self.state.db.cursor()
        cur.execute(
            "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
            (self.state.selection.id,),
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
                (self.state.selection.id, work_id),
            )
            note_row = cur.fetchone()
            note = note_row[0] if note_row and note_row[0] else ""

        self._enter_editor_mode(
            EditTarget(kind="entity_note", id=self.state.selection.id),
            f"Note: {entity_type} {name}",
            note,
        )

    def action_edit_block(self) -> None:
        if self.state is None:
            return
        if self.state.view != "outline":
            return
        if self.state.selection.kind != "block" or not self.state.selection.id:
            return

        cur = self.state.db.cursor()
        cur.execute(
            "SELECT language, source_text FROM blocks WHERE id = %s",
            (self.state.selection.id,),
        )
        row = cur.fetchone()
        if row is None:
            return
        lang, text = row

        self._enter_editor_mode(
            EditTarget(kind="block_text", id=self.state.selection.id),
            f"Block ({lang})",
            text,
        )

    def action_add_item(self) -> None:
        if self.state is None:
            return
        if self.state.view != "outline":
            return

        import uuid

        cur = self.state.db.cursor()

        if self.state.nav_level == "documents":
            title = f"Doc {uuid.uuid4().hex[:8]}"
            doc_id = str(uuid.uuid4())
            work_id = self.state.work["work"]["id"]
            cur.execute(
                "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
                (doc_id, work_id, title),
            )
            self.state.db.commit()
            self.state.selection = Selection(kind="document", id=doc_id)
            self._render_view()

        elif self.state.nav_level == "sections":
            if not self.state.document_id:
                return
            title = f"Sec {uuid.uuid4().hex[:8]}"
            section_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO sections (id, document_id, title, order_index) VALUES (%s, %s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1))",
                (section_id, self.state.document_id, title, self.state.document_id),
            )
            self.state.db.commit()
            self.state.selection = Selection(kind="section", id=section_id)
            self._render_view()

        elif self.state.nav_level == "blocks":
            if not self.state.section_id:
                return
            block_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO blocks (id, section_id, block_type, language, source_text) VALUES (%s, %s, 'paragraph', 'en', '(new block)')",
                (block_id, self.state.section_id),
            )
            self.state.db.commit()
            self.state.selection = Selection(kind="block", id=block_id)
            self._render_view()

    def action_save(self) -> None:
        if self.state is None:
            return
        if self.state.view != "editor":
            return

        editor_widget = self.screen.query_one("#editor")
        new_text = getattr(editor_widget, "text", None)
        if new_text is None:
            new_text = getattr(editor_widget, "value", "")

        saved = False
        if self.state.editor_entity_id:
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
                (self.state.editor_entity_id, work_id, json.dumps({"note": new_text})),
            )
            self.state.db.commit()
            self.state.undo_redo.record(
                EditTarget(kind="entity_note", id=self.state.editor_entity_id),
                self.state.editor_text,
                new_text,
            )
            self.state.view = "entities"
            saved = True
        elif self.state.editor_block_id:
            cur = self.state.db.cursor()
            cur.execute(
                "UPDATE blocks SET source_text = %s WHERE id = %s",
                (new_text, self.state.editor_block_id),
            )
            self.state.db.commit()
            self.state.undo_redo.record(
                EditTarget(kind="block_text", id=self.state.editor_block_id),
                self.state.editor_text,
                new_text,
            )
            self.state.view = "outline"
            saved = True

        if saved:
            self.state.mode = "browse"
            self.state.editor_title = None
            self.state.editor_entity_id = None
            self.state.editor_block_id = None
            self.state.editor_block_lang = None
            self.state.editor_text = ""
            self._render_view()

    def action_undo(self) -> None:
        if self.state is None or self.state.view != "editor":
            return
        edit = self.state.undo_redo.pop_undo()
        if edit is None:
            return
        self.state.editor_text = edit.new
        editor_widget = self.screen.query_one("#editor")
        if hasattr(editor_widget, "text"):
            editor_widget.text = edit.new
        else:
            editor_widget.value = edit.new
        self._render_view()

    def action_redo(self) -> None:
        if self.state is None or self.state.view != "editor":
            return
        edit = self.state.undo_redo.pop_redo()
        if edit is None:
            return
        self.state.editor_text = edit.new
        editor_widget = self.screen.query_one("#editor")
        if hasattr(editor_widget, "text"):
            editor_widget.text = edit.new
        else:
            editor_widget.value = edit.new
        self._render_view()

    def action_back(self) -> None:
        if self.state is None:
            return

        if self.state.view == "editor":
            if self.state.editor_entity_id:
                self.state.view = "entities"
            else:
                self.state.view = "outline"
            self.state.mode = "browse"
            self.state.editor_title = None
            self.state.editor_entity_id = None
            self.state.editor_block_id = None
            self.state.editor_block_lang = None
            self.state.editor_text = ""
            self._render_view()
            return

        if self.state.view == "entities":
            if self.state.selection.kind == "entity":
                self.state.selection = Selection()
                self._render_view()
                return
            self.state.view = "outline"
            self._clear_undo_redo_on_view_change()
            self._render_view()
            return

        if self.state.nav_level == "blocks":
            self.state.nav_level = "sections"
            self.state.section_id = None
            self.state.selection = Selection()
            self._render_view()
            return

        if self.state.nav_level == "sections":
            self.state.nav_level = "documents"
            self.state.document_id = None
            self.state.selection = Selection()
            self._render_view()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.state is None:
            return

        item_id = event.item.id
        if item_id is None:
            return

        if self.state.view == "entities":
            self.state.selection = Selection(kind="entity", id=item_id)
            self._render_view()
            return

        if self.state.view != "outline":
            return

        if self.state.nav_level == "documents":
            self.state.document_id = item_id
            self.state.nav_level = "sections"
            self.state.selection = Selection(kind="document", id=item_id)
            self._render_view()
            return

        if self.state.nav_level == "sections":
            self.state.section_id = item_id
            self.state.nav_level = "blocks"
            self.state.selection = Selection(kind="section", id=item_id)
            self._render_view()
            return

        self.state.selection = Selection(kind="block", id=item_id)
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

    def _clear_undo_redo_on_view_change(self) -> None:
        if self.state is None:
            return
        self.state.undo_redo.clear()

    def _enter_editor_mode(self, target: EditTarget, title: str, text: str) -> None:
        self.state.editor_title = title
        self.state.editor_text = text
        self.state.view = "editor"
        self.state.mode = "edit"
        if target.kind == "entity_note":
            self.state.editor_entity_id = target.id
            self.state.editor_block_id = None
            self.state.editor_block_lang = None
        elif target.kind == "block_text":
            self.state.editor_block_id = target.id
            self.state.editor_block_lang = ""
            self.state.editor_entity_id = None
        else:
            return
        self._render_view()

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


if __name__ == "__main__":
    LitteraApp().run()
