"""Littera TUI application with Elm-inspired architecture.

- Clean path-based navigation (work -> document -> section -> block)
- Isolated edit_session for editing overlay
- Unified selection model
- Views are pure functions of state (no DB queries)
- DB reads in queries.py, DB writes in actions.py
"""

from __future__ import annotations

from pathlib import Path
import logging

import yaml

from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, ListView
from textual.containers import Horizontal

from littera.tui.state import (
    AppState,
    PathElement,
    EditTarget,
    GotoOutline,
    GotoEntities,
    GotoReviews,
    ExitEditor,
    OutlinePush,
    OutlinePop,
    OutlineSelect,
    EntitiesSelect,
    EntitiesClearSelection,
    ReviewsSelect,
    ReviewsClearSelection,
    ClearSelection,
    StartEdit,
)

from littera.tui.views.entities import EntitiesView
from littera.tui.views.editor import EditorView
from littera.tui.views.outline import OutlineView
from littera.tui.views.reviews import ReviewsView
from littera.tui.views.input_dialog import InputDialog, ConfirmDialog, RecoveryDialog
from littera.tui.decorators import safe_action
from littera.tui import queries, actions

from littera.db.bootstrap import (
    start_postgres,
    stop_postgres,
    WalCorruptionError,
    find_pg_resetwal,
    reset_wal,
    reinit_cluster,
    ensure_database,
)
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
        ("L", "add_label", "Add Label"),
        ("ctrl+shift+l", "delete_label", "Delete Label"),
        ("p", "set_property", "Set Property"),
        ("ctrl+shift+p", "delete_property", "Delete Property"),
        ("M", "show_mentions", "Show Mentions"),
        ("ctrl+shift+d", "delete_mention", "Delete Mention"),
        ("R", "reviews", "Reviews"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state: AppState | None = None
        self.views = {}
        self._pg_cfg = None
        self._pg_started_here = False
        self._work_cfg: dict = {}
        self._suppress_editor_change_events = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(id="main")
        yield Footer()

    def on_mount(self) -> None:
        littera_dir = Path.cwd() / ".littera"
        if not littera_dir.exists():
            return  # Or show error, but usually fails earlier

        logging.basicConfig(
            filename=littera_dir / "tui.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        self._work_cfg = self._load_cfg()

        EmbeddedPostgresManager(littera_dir).ensure()

        pg_cfg = postgres_config_from_work(littera_dir, self._work_cfg)
        self._pg_cfg = pg_cfg

        try:
            self._pg_started_here = start_postgres(pg_cfg)
        except WalCorruptionError as e:
            can_recover = find_pg_resetwal(pg_cfg) is not None
            self._handle_wal_corruption(pg_cfg, e, can_recover)
            return

        self._finish_init(pg_cfg, self._work_cfg)

    def _finish_init(self, pg_cfg, cfg: dict) -> None:
        """Complete TUI initialization after PG is running."""
        import psycopg

        conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)

        self.state = AppState(work=cfg, db=conn)
        self.views = {
            "outline": OutlineView(),
            "entities": EntitiesView(),
            "editor": EditorView(),
            "reviews": ReviewsView(),
        }
        self._render_view()

    def _handle_wal_corruption(
        self, pg_cfg, error: WalCorruptionError, can_recover: bool
    ) -> None:
        """Show recovery dialog and act on user's choice."""
        message = (
            f"{error}\n\n"
            "Recent log output:\n"
            f"{error.log_tail}"
        )

        def on_choice(choice: str) -> None:
            if choice == "recover":
                self._attempt_wal_recovery(pg_cfg)
            elif choice == "reinit":
                self._attempt_reinit(pg_cfg)
            else:
                self.exit()

        self.push_screen(RecoveryDialog(message, can_recover), on_choice)

    def _attempt_wal_recovery(self, pg_cfg) -> None:
        """Run pg_resetwal, restart PG, and continue init."""
        try:
            reset_wal(pg_cfg)
            self._pg_started_here = start_postgres(pg_cfg)
            self._finish_init(pg_cfg, self._work_cfg)
        except Exception as e:
            logging.exception("WAL recovery failed")
            self.notify(f"Recovery failed: {e}", severity="error")
            self.exit()

    def _attempt_reinit(self, pg_cfg) -> None:
        """Delete pgdata, reinit, recreate DB + schema, continue init."""
        try:
            reinit_cluster(pg_cfg)
            self._pg_started_here = start_postgres(pg_cfg)
            ensure_database(pg_cfg)

            from littera.db.migrate import migrate
            import psycopg

            conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)
            migrate(conn)
            conn.close()

            self._finish_init(pg_cfg, self._work_cfg)
        except Exception as e:
            logging.exception("Re-initialization failed")
            self.notify(f"Re-initialization failed: {e}", severity="error")
            self.exit()

    def on_unmount(self) -> None:
        if self.state is not None:
            self.state.db.close()

        if (
            getattr(self, "_pg_started_here", False)
            and getattr(self, "_pg_cfg", None) is not None
        ):
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

    def action_reviews(self) -> None:
        if self.state is None:
            return
        self.state.dispatch(GotoReviews())
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

        if sel.kind in ("document", "section"):
            title = queries.fetch_item_title(self.state.db, sel.kind, sel.id)
            self.state.dispatch(
                OutlinePush(PathElement(kind=sel.kind, id=sel.id, title=title))
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

        if self.state.view == "reviews":
            if self.state.reviews.selection.kind == "review":
                self.state.dispatch(ReviewsClearSelection())
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
        """Add document/section/block/review at current level."""
        if self.state is None:
            return

        if self.state.view == "entities":
            self._prompt_add_entity()
            return

        if self.state.view == "reviews":
            self._prompt_add_review()
            return

        if self.state.view != "outline":
            return

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
        entity_id = actions.create_entity(self.state.db, entity_type, name)
        if entity_id is None:
            return
        self.state.dispatch(EntitiesSelect(entity_id))
        self._render_view()

    @safe_action
    def _create_document(self, title: str) -> None:
        if self.state is None or self.state.work is None:
            return
        work_id = self.state.work.get("work", {}).get("id")
        if work_id is None:
            return
        doc_id = actions.create_document(self.state.db, work_id, title)
        self.state.dispatch(OutlineSelect(kind="document", item_id=doc_id))
        self._render_view()

    @safe_action
    def _create_section(self, title: str) -> None:
        if self.state is None:
            return
        doc = self.state.current_document
        if not doc:
            return
        section_id = actions.create_section(self.state.db, doc.id, title)
        self.state.dispatch(OutlineSelect(kind="section", item_id=section_id))
        self._render_view()

    @safe_action
    def _create_block(self) -> None:
        if self.state is None:
            return
        section = self.state.current_section
        if not section:
            return
        block_id = actions.create_block(self.state.db, section.id)
        self.state.dispatch(OutlineSelect(kind="block", item_id=block_id))
        self._render_view()

    @safe_action
    def _prompt_add_review(self) -> None:
        """Chain dialogs to create a review: description then severity."""

        async def on_desc_result(description: str | None) -> None:
            if not description:
                return

            async def on_severity_result(severity: str | None) -> None:
                if not severity:
                    return
                severity = severity.strip().lower()
                if severity not in ("low", "medium", "high"):
                    self.notify("Severity must be low, medium, or high", severity="warning")
                    return
                self._create_review(description, severity)

            self.push_screen(
                InputDialog("New Review", "Severity (low/medium/high):", "medium"),
                on_severity_result,
            )

        self.push_screen(
            InputDialog("New Review", "Description:", ""),
            on_desc_result,
        )

    @safe_action
    def _create_review(self, description: str, severity: str) -> None:
        if self.state is None or self.state.work is None:
            return
        work_id = self.state.work.get("work", {}).get("id")
        if work_id is None:
            return
        review_id = actions.create_review(self.state.db, work_id, description, severity)
        self.state.dispatch(ReviewsSelect(review_id))
        self._render_view()

    @safe_action
    def _delete_review(self) -> None:
        """Delete the selected review with confirmation."""
        if self.state is None:
            return
        sel = self.state.reviews.selection
        if not sel or sel.kind != "review" or not sel.id:
            return

        review_id = sel.id

        async def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            actions.delete_review(self.state.db, review_id)
            self.state.dispatch(ClearSelection())
            self._render_view()

        self.push_screen(
            ConfirmDialog("Delete Review?", "This cannot be undone."),
            on_confirm,
        )

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

        current_title = queries.fetch_item_title(self.state.db, sel.kind, sel.id)
        kind_label = sel.kind.title()
        kind = sel.kind
        item_id = sel.id

        async def on_title_result(title: str | None) -> None:
            if title is None:
                return
            actions.update_title(self.state.db, kind, item_id, title)
            self._render_view()

        self.push_screen(
            InputDialog(f"Edit {kind_label}", "New title:", current_title),
            on_title_result,
        )

    @safe_action
    def action_delete_item(self) -> None:
        """Delete selected document/section/block or review."""
        if self.state is None:
            return

        if self.state.view == "reviews":
            self._delete_review()
            return

        if self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if not sel.id:
            return
        if sel.kind not in ("document", "section", "block"):
            return

        kind_label = sel.kind.title()
        kind = sel.kind
        item_id = sel.id

        async def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            actions.delete_item(self.state.db, kind, item_id)
            self.state.dispatch(ClearSelection())
            self._render_view()

        self.push_screen(
            ConfirmDialog(f"Delete {kind_label}?", "This cannot be undone."),
            on_confirm,
        )

    @safe_action
    def action_link_entity(self) -> None:
        """Link selected block to an entity."""
        if self.state is None or self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if not sel or sel.kind != "block" or not sel.id:
            return

        block_id = sel.id

        async def on_name_result(name: str | None) -> None:
            if not name:
                return
            try:
                actions.link_entity(self.state.db, block_id, name)
            except LookupError:
                return
            if hasattr(self, "notify"):
                self.notify(f"Linked to {name}")

        self.push_screen(
            InputDialog("Link to Entity", "Entity Name:", ""), on_name_result
        )

    # =====================
    # Entity labels & properties
    # =====================

    @safe_action
    def action_add_label(self) -> None:
        """Add a label to the selected entity."""
        if self.state is None or self.state.view != "entities":
            return
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return

        entity_id = sel.id

        async def on_lang_result(language: str | None) -> None:
            if not language:
                return

            async def on_form_result(base_form: str | None) -> None:
                if not base_form:
                    return
                actions.add_entity_label(self.state.db, entity_id, language, base_form)
                self._render_view()

            self.push_screen(
                InputDialog("Add Label", "Base form:", ""),
                on_form_result,
            )

        self.push_screen(
            InputDialog("Add Label", "Language (e.g. en, pl):", ""),
            on_lang_result,
        )

    @safe_action
    def action_delete_label(self) -> None:
        """Delete a label from the selected entity by language."""
        if self.state is None or self.state.view != "entities":
            return
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return

        entity_id = sel.id

        async def on_lang_result(language: str | None) -> None:
            if not language:
                return
            deleted = actions.delete_entity_label(self.state.db, entity_id, language)
            if deleted:
                self.notify(f"Label deleted ({language})")
            else:
                self.notify(f"No {language} label found", severity="warning")
            self._render_view()

        self.push_screen(
            InputDialog("Delete Label", "Language to delete:", ""),
            on_lang_result,
        )

    @safe_action
    def action_set_property(self) -> None:
        """Set a property on the selected entity."""
        if self.state is None or self.state.view != "entities":
            return
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return

        entity_id = sel.id

        async def on_kv_result(kv: str | None) -> None:
            if not kv or "=" not in kv:
                if kv:
                    self.notify("Format: key=value", severity="warning")
                return
            key, value = kv.split("=", 1)
            actions.set_entity_property(self.state.db, entity_id, key, value)
            self.notify(f"Property set: {key}={value}")
            self._render_view()

        self.push_screen(
            InputDialog("Set Property", "key=value:", ""),
            on_kv_result,
        )

    @safe_action
    def action_delete_property(self) -> None:
        """Delete a property from the selected entity."""
        if self.state is None or self.state.view != "entities":
            return
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return

        entity_id = sel.id

        async def on_key_result(key: str | None) -> None:
            if not key:
                return
            deleted = actions.delete_entity_property(self.state.db, entity_id, key)
            if deleted:
                self.notify(f"Property deleted: {key}")
            else:
                self.notify(f"Property '{key}' not found", severity="warning")
            self._render_view()

        self.push_screen(
            InputDialog("Delete Property", "Property key:", ""),
            on_key_result,
        )

    # =====================
    # Mention management
    # =====================

    @safe_action
    def action_show_mentions(self) -> None:
        """Show mentions for the selected block in detail panel."""
        if self.state is None or self.state.view != "outline":
            return
        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        mentions = queries.fetch_block_mentions(self.state.db, sel.id)
        if not mentions:
            self.notify("No mentions for this block")
            return

        lines = ["Mentions for this block:", ""]
        for i, (mid, etype, elabel, lang) in enumerate(mentions, 1):
            lines.append(f"  {i}. {etype} {elabel} ({lang})")
        lines.append("")
        lines.append("ctrl+shift+d: delete mention by number")

        self.state.outline.detail = "\n".join(lines)
        self._render_view()

    @safe_action
    def action_delete_mention(self) -> None:
        """Delete a mention from the selected block by number."""
        if self.state is None or self.state.view != "outline":
            return
        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        block_id = sel.id
        mentions = queries.fetch_block_mentions(self.state.db, block_id)
        if not mentions:
            self.notify("No mentions to delete")
            return

        async def on_num_result(num_str: str | None) -> None:
            if not num_str or not num_str.isdigit():
                return
            idx = int(num_str)
            if idx < 1 or idx > len(mentions):
                self.notify(f"Invalid mention number (1-{len(mentions)})", severity="warning")
                return
            mention_id = mentions[idx - 1][0]
            actions.delete_mention(self.state.db, mention_id)
            self.notify("Mention deleted")
            self._render_view()

        self.push_screen(
            InputDialog("Delete Mention", f"Mention # (1-{len(mentions)}):", ""),
            on_num_result,
        )

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

        work_id = self.state.work.get("work", {}).get("id") if self.state.work else None
        try:
            entity_type, name, note = queries.fetch_entity_note(
                self.state.db, sel.id, work_id
            )
        except LookupError:
            return

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

        try:
            lang, text = queries.fetch_block_text(self.state.db, sel.id)
        except LookupError:
            return

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

        new_text = self._get_editor_text()

        if session.target.kind == "entity_note":
            work_id = self.state.work.get("work", {}).get("id") if self.state.work else None
            if work_id is None:
                return
            actions.save_entity_note(self.state.db, session.target.id, work_id, new_text)

        elif session.target.kind == "block_text":
            actions.save_block_text(self.state.db, session.target.id, new_text)

        else:
            return

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
        self._set_editor_text(session.current_text)

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
        self._set_editor_text(session.current_text)

    # =====================
    # Internal helpers
    # =====================

    def _start_edit(self, target: EditTarget, title: str, text: str) -> None:
        if self.state is None:
            return

        self.state.undo_redo.clear()

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

    def _get_editor_text(self) -> str:
        """Read current text from the editor widget."""
        if self.state is None:
            return ""
        session = self.state.edit_session
        fallback = session.current_text if session else ""
        try:
            widget = self.screen.query_one("#editor")
            if hasattr(widget, "text"):
                return str(widget.text)
            if hasattr(widget, "value"):
                return str(widget.value)
        except NoMatches:
            pass
        return str(fallback)

    def _set_editor_text(self, text: str) -> None:
        """Write text into the editor widget, suppressing change events."""
        try:
            widget = self.screen.query_one("#editor")
        except NoMatches:
            return

        self._suppress_editor_change_events = True
        try:
            if hasattr(widget, "text"):
                widget.text = text
            elif hasattr(widget, "value"):
                widget.value = text
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

    def _refresh_data(self) -> None:
        """Pre-load view data from DB into state before rendering."""
        if self.state is None:
            return
        if self.state.view == "outline":
            queries.refresh_outline(self.state)
        elif self.state.view == "entities":
            queries.refresh_entities(self.state)
        elif self.state.view == "reviews":
            queries.refresh_reviews(self.state)

    async def _render_view_async(self) -> None:
        if self.state is None:
            return

        self._refresh_data()

        try:
            container = self.screen.query_one("#main")
        except NoMatches:
            return

        await container.remove_children()

        view = self.views[self.state.view]
        widgets = view.render(self.state)
        await container.mount_all(widgets)

        # Focus the appropriate widget for each view
        if self.state.view == "editor":
            try:
                editor = self.screen.query_one("#editor")
                editor.focus()
            except NoMatches:
                pass
        elif self.state.view in ("outline", "entities", "reviews"):
            try:
                nav = self.screen.query_one("#nav")
                nav.focus()
            except NoMatches:
                pass

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
        if prefix in {"doc", "sec", "blk", "ent", "rev"}:
            return prefix, rest
        return None, raw

    def _set_selection_from_list_item(self, item_id: str) -> bool:
        """Set selection based on list item id.

        Returns True if selection changed.
        """

        if self.state is None:
            return False

        if self.state.view == "reviews":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            review_id = raw_uuid if prefix == "rev" else item_id

            current = self.state.reviews.selection
            if current.kind == "review" and current.id == review_id:
                return False

            self.state.dispatch(ReviewsSelect(review_id))
            return True

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

if __name__ == "__main__":
    LitteraApp().run()
