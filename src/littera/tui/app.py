"""Littera TUI application with refactored state architecture.

- Clean path-based navigation (work -> document -> section -> block)
- Isolated edit_session for editing overlay
- Unified selection model
"""

from __future__ import annotations

from pathlib import Path
import logging

import yaml

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Footer, Header, ListView
from textual.containers import Horizontal

from littera.tui.state import (
    AppState,
    PathElement,
    Selection,
    EditTarget,
    EditSession,
    GotoOutline,
    GotoEntities,
    ExitEditor,
    OutlinePush,
    OutlinePop,
    OutlineSelect,
    EntitiesSelect,
    EntitiesClearSelection,
    ClearSelection,
    StartEdit,
)


from littera.tui.views.entities import EntitiesView
from littera.tui.views.editor import EditorView
from littera.tui.views.outline import OutlineView
from littera.tui.views.input_dialog import InputDialog, ConfirmDialog
from littera.tui.decorators import safe_action

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
        ("ctrl+e", "edit_title", "Edit Title"),
        ("d", "delete_item", "Delete"),
        ("l", "link_entity", "Link Entity"),
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
        self._suppress_editor_change_events = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(id="main")
        yield Footer()

    @safe_action
    def on_mount(self) -> None:
        littera_dir = Path.cwd() / ".littera"
        if not littera_dir.exists():
            return  # Or show error, but usually fails earlier

        logging.basicConfig(
            filename=littera_dir / "tui.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        cfg = self._load_cfg()

        import psycopg

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
        self.state.dispatch(GotoOutline())
        self.state.dispatch(ExitEditor())
        self._clear_undo_redo()
        self._render_view()

    def action_entities(self) -> None:
        if self.state is None:
            return
        self.state.dispatch(GotoEntities())
        self.state.dispatch(ExitEditor())
        self._clear_undo_redo()
        self._render_view()

    # =====================
    # Navigation
    # =====================

    @safe_action
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
            self.state.dispatch(
                OutlinePush(PathElement(kind="document", id=sel.id, title=title))
            )
            self._render_view()

        elif sel.kind == "section":
            cur.execute("SELECT title FROM sections WHERE id = %s", (sel.id,))
            row = cur.fetchone()
            title = row[0] if row else "Untitled"
            self.state.dispatch(
                OutlinePush(PathElement(kind="section", id=sel.id, title=title))
            )
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
            if self.state.entities.selection.kind == "entity":
                self.state.dispatch(EntitiesClearSelection())
                self._render_view()
                return
            self.action_outline()
            return

        # Outline view: pop path
        if self.state.outline.path:
            self.state.dispatch(OutlinePop())
            self._render_view()

    # =====================
    # Creation
    # =====================

    @safe_action
    def action_add_item(self) -> None:
        """Add document/section/block at current level."""
        if self.state is None:
            return

        # Handle Entities View
        if self.state.view == "entities":
            self._prompt_add_entity()
            return

        if self.state.view != "outline":
            return

        import uuid

        cur = self.state.db.cursor()
        nav_level = self.state.nav_level

        if nav_level == "documents":

            async def on_title_result(title: str | None) -> None:
                if title is None:
                    return
                self._create_document(title)

            self.push_screen(
                InputDialog("New Document", "Title:", ""),
                on_title_result,
            )
        elif nav_level == "sections":

            async def on_title_result(title: str | None) -> None:
                if title is None:
                    return
                self._create_section(title)

            self.push_screen(
                InputDialog("New Section", "Title:", ""),
                on_title_result,
            )
        elif nav_level == "blocks":
            self._create_block()

    @safe_action
    def _prompt_add_entity(self) -> None:
        """Chain dialogs to create an entity."""

        async def on_type_result(entity_type: str | None) -> None:
            if not entity_type:
                return

            async def on_name_result(name: str | None) -> None:
                if not name:
                    return
                self._create_entity(entity_type, name)

            self.push_screen(
                InputDialog("New Entity", "Name:", ""),
                on_name_result,
            )

        self.push_screen(
            InputDialog("New Entity", "Type (e.g. concept):", "concept"),
            on_type_result,
        )

    @safe_action
    def _create_entity(self, entity_type: str, name: str) -> None:
        if self.state is None:
            return

        cur = self.state.db.cursor()
        cur.execute(
            "INSERT INTO entities (entity_type, canonical_label) VALUES (%s, %s) RETURNING id",
            (entity_type, name),
        )
        entity_id = str(cur.fetchone()[0])
        self.state.db.commit()

        self.state.dispatch(EntitiesSelect(entity_id))
        self._render_view()

    @safe_action
    def _create_document(self, title: str) -> None:
        if self.state is None:
            return
        import uuid

        cur = self.state.db.cursor()
        doc_id = str(uuid.uuid4())
        work_id = self.state.work["work"]["id"]
        cur.execute(
            "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
            (doc_id, work_id, title),
        )
        self.state.db.commit()
        self.state.dispatch(OutlineSelect(kind="document", item_id=doc_id))
        self._render_view()

    @safe_action
    def _create_section(self, title: str) -> None:
        if self.state is None:
            return
        doc = self.state.current_document
        if not doc:
            return
        import uuid

        cur = self.state.db.cursor()
        section_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO sections (id, document_id, title, order_index) VALUES (%s, %s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1))",
            (section_id, doc.id, title, doc.id),
        )
        self.state.db.commit()
        self.state.dispatch(OutlineSelect(kind="section", item_id=section_id))
        self._render_view()

    @safe_action
    def _create_block(self) -> None:
        if self.state is None:
            return
        section = self.state.current_section
        if not section:
            return
        import uuid

        cur = self.state.db.cursor()
        block_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO blocks (id, section_id, block_type, language, source_text) VALUES (%s, %s, 'paragraph', 'en', '(new block)')",
            (block_id, section.id),
        )
        self.state.db.commit()
        self.state.dispatch(OutlineSelect(kind="block", item_id=block_id))
        self._render_view()

    @safe_action
    def action_edit_title(self) -> None:
        """Edit title of selected document or section."""
        if self.state is None:
            return
        if self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if sel.kind not in ("document", "section") or not sel.id:
            return

        cur = self.state.db.cursor()
        table = "documents" if sel.kind == "document" else "sections"
        cur.execute(f"SELECT title FROM {table} WHERE id = %s", (sel.id,))
        row = cur.fetchone()
        current_title = row[0] if row and row[0] else ""

        kind_label = sel.kind.title()

        async def on_title_result(title: str | None) -> None:
            if title is None:
                return
            self._update_title(table, title, sel.id)

        self.push_screen(
            InputDialog(f"Edit {kind_label}", "New title:", current_title),
            on_title_result,
        )

    @safe_action
    def _update_title(self, table: str, title: str, item_id: str) -> None:
        if self.state is None:
            return
        cur = self.state.db.cursor()
        cur.execute(
            f"UPDATE {table} SET title = %s WHERE id = %s",
            (title, item_id),
        )
        self.state.db.commit()
        self._render_view()

    @safe_action
    def action_delete_item(self) -> None:
        """Delete selected document/section/block."""
        if self.state is None:
            return
        if self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if not sel.id:
            return

        table_map = {
            "document": "documents",
            "section": "sections",
            "block": "blocks",
        }
        table = table_map.get(sel.kind)
        if not table:
            return

        kind_label = sel.kind.title()

        async def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            self._perform_delete(table, sel.id)

        self.push_screen(
            ConfirmDialog(f"Delete {kind_label}?", "This cannot be undone."),
            on_confirm,
        )

    @safe_action
    def _perform_delete(self, table: str, item_id: str) -> None:
        if self.state is None:
            return
        cur = self.state.db.cursor()
        cur.execute(f"DELETE FROM {table} WHERE id = %s", (item_id,))
        self.state.db.commit()
        self.state.dispatch(ClearSelection())
        self._render_view()

    @safe_action
    def action_link_entity(self) -> None:
        """Link selected block to an entity."""
        if self.state is None or self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if not sel or sel.kind != "block" or not sel.id:
            return

        async def on_name_result(name: str | None) -> None:
            if not name:
                return
            self._perform_link(sel.id, name)

        self.push_screen(
            InputDialog("Link to Entity", "Entity Name:", ""), on_name_result
        )

    @safe_action
    def _perform_link(self, block_id: str, entity_name: str) -> None:
        if self.state is None:
            return
        cur = self.state.db.cursor()

        # Resolve entity
        cur.execute(
            "SELECT id FROM entities WHERE canonical_label = %s", (entity_name,)
        )
        row = cur.fetchone()

        if row:
            entity_id = row[0]
        else:
            # Auto-create
            cur.execute(
                "INSERT INTO entities (entity_type, canonical_label) VALUES ('concept', %s) RETURNING id",
                (entity_name,),
            )
            entity_id = str(cur.fetchone()[0])

        # Link (mentions require language per schema)
        cur.execute("SELECT language FROM blocks WHERE id = %s", (block_id,))
        row = cur.fetchone()
        if row is None:
            return
        (language,) = row

        cur.execute(
            "SELECT 1 FROM mentions WHERE block_id = %s AND entity_id = %s AND language = %s",
            (block_id, entity_id, language),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO mentions (block_id, entity_id, language) VALUES (%s, %s, %s)",
                (block_id, entity_id, language),
            )
        self.state.db.commit()

        if hasattr(self, "notify"):
            self.notify(f"Linked to {entity_name}")

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
        try:
            editor_widget = self.screen.query_one("#editor")
            if hasattr(editor_widget, "text"):
                new_text = editor_widget.text
            elif hasattr(editor_widget, "value"):
                new_text = editor_widget.value
        except Exception:
            pass

        new_text = str(new_text)

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
            self.state.dispatch(ExitEditor())
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
            self.state.dispatch(ExitEditor())
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

        session.current_text = edit.old
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
        if self.state is None:
            return

        # Reset editor-local undo/redo for the new session.
        self.state.undo_redo.clear()

        # Keep a single entry-point for editor overlay state.
        return_to = "entities" if target.kind == "entity_note" else "outline"
        self.state.dispatch(StartEdit(target=target, text=text, return_to=return_to))
        self._render_view()

    def _cancel_edit(self) -> None:
        if self.state is None:
            return
        session = self.state.edit_session
        if session is None:
            return

        self.state.dispatch(ExitEditor())
        self._render_view()

    def _clear_undo_redo(self) -> None:
        if self.state is None:
            return
        self.state.undo_redo.clear()

    def _update_editor_widget(self, text: str) -> None:
        try:
            editor_widget = self.screen.query_one("#editor")
        except Exception:
            return

        self._suppress_editor_change_events = True
        try:
            if hasattr(editor_widget, "text"):
                editor_widget.text = text
            elif hasattr(editor_widget, "value"):
                editor_widget.value = text
        finally:
            self._suppress_editor_change_events = False

    def _render_view(self) -> None:
        """Schedule a view re-render.

        Textual's `remove_children()` / `mount()` are async. If we call them
        synchronously, removals are deferred and we can briefly have duplicate ids
        in the DOM (crash on start / fast navigation).
        """

        if self.state is None:
            return

        self.run_worker(
            self._render_view_async(),
            group="render",
            exclusive=True,
            exit_on_error=False,
        )

    async def _render_view_async(self) -> None:
        if self.state is None:
            return

        try:
            container = self.screen.query_one("#main")
        except Exception:
            return

        await container.remove_children()

        view = self.views[self.state.view]
        widgets = view.render(self.state)
        await container.mount_all(widgets)

    def _load_cfg(self) -> dict:
        work_dir = Path.cwd()
        littera_dir = work_dir / ".littera"
        if not littera_dir.exists():
            raise RuntimeError("Not a Littera work")
        return yaml.safe_load((littera_dir / "config.yml").read_text())

    # =====================
    # Event handlers
    # =====================

    def _record_editor_change(self, new_text: str) -> None:
        if self.state is None or self.state.view != "editor":
            return
        if self._suppress_editor_change_events:
            return
        session = self.state.edit_session
        if session is None:
            return

        old_text = session.current_text
        if new_text == old_text:
            return

        self.state.undo_redo.record(session.target, old_text, new_text)
        session.current_text = new_text

    @safe_action
    def on_text_area_changed(self, event) -> None:
        # Textual 7: event is TextArea.Changed and exposes event.text_area
        text_area = getattr(event, "text_area", None)
        if text_area is None or getattr(text_area, "id", None) != "editor":
            return
        new_text = getattr(text_area, "text", None)
        if new_text is None:
            new_text = getattr(text_area, "value", "")
        self._record_editor_change(str(new_text))

    @safe_action
    def on_input_changed(self, event) -> None:
        # Covers Input fallback editor; ignore dialogs (id != editor)
        input_widget = getattr(event, "input", None)
        if input_widget is None or getattr(input_widget, "id", None) != "editor":
            return
        new_text = getattr(event, "value", None)
        if new_text is None:
            new_text = getattr(input_widget, "value", "")
        self._record_editor_change(str(new_text))

    def _parse_widget_id(self, raw: str) -> tuple[str | None, str]:
        # Textual ids can't start with a digit, so we prefix UUIDs.
        if "-" not in raw:
            return None, raw
        prefix, rest = raw.split("-", 1)
        if prefix in {"doc", "sec", "blk", "ent"}:
            return prefix, rest
        return None, raw

    def _set_selection_from_list_item(self, item_id: str) -> bool:
        """Set selection based on list item id.

        Returns True if selection changed.
        """

        if self.state is None:
            return False

        if self.state.view == "entities":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            entity_id = raw_uuid if prefix == "ent" else item_id

            current = self.state.entities.selection
            if current.kind == "entity" and current.id == entity_id:
                return False

            self.state.dispatch(EntitiesSelect(entity_id))
            return True

        if self.state.view == "outline":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            prefix_kind_map = {
                "doc": "document",
                "sec": "section",
                "blk": "block",
            }

            if prefix in prefix_kind_map:
                kind = prefix_kind_map[prefix]
                raw_id = raw_uuid
            else:
                # Fallback: infer kind from current nav_level
                nav_level = self.state.nav_level
                kind_map = {
                    "documents": "document",
                    "sections": "section",
                    "blocks": "block",
                }
                kind = kind_map.get(nav_level, "document")
                raw_id = item_id

            current = self.state.outline.selection
            if current.kind == kind and current.id == raw_id:
                return False

            self.state.dispatch(OutlineSelect(kind=kind, item_id=raw_id))
            return True

        return False

    @safe_action
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update selection and right-hand detail on highlight."""
        if self.state is None:
            return

        item_id = event.item.id
        if item_id is None:
            return

        changed = self._set_selection_from_list_item(str(item_id))
        if changed:
            self._render_view()

    @safe_action
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Drill down on activation (Enter/click)."""
        if self.state is None:
            return

        item_id = event.item.id
        if item_id is None:
            return

        self._set_selection_from_list_item(str(item_id))

        if self.state.view == "outline":
            # In Textual, Enter is often consumed by ListView to emit Selected.
            # Treat this as the user's "drill down" gesture.
            self.action_enter()
            return

        self._render_view()

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.action_back()
        elif event.key == "^p":
            self.action_show_palette()

    @safe_action
    def action_show_palette(self) -> None:
        if self.state is None:
            return
        self.app.bell()
        self.app.exit()


if __name__ == "__main__":
    LitteraApp().run()
