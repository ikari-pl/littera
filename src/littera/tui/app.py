"""Littera TUI application with Elm-inspired architecture.

- Clean path-based navigation (work -> document -> section -> block)
- Isolated edit_session for editing overlay
- Unified selection model
- Views are pure functions of state (no DB queries)
- DB reads in queries.py, DB writes in actions.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

import psycopg
import yaml
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, ListView, Static

from littera.cli.review import VALID_SEVERITIES, ReviewUpdateError
from littera.db.bootstrap import (
    WalCorruptionError,
    ensure_database,
    find_pg_resetwal,
    reinit_cluster,
    reset_wal,
    start_postgres,
    stop_postgres,
)
from littera.db.embedded_pg import EmbeddedPostgresManager
from littera.db.migrate import migrate
from littera.db.workdb import (
    pg_lease_seconds,
    postgres_config_from_work,
    release_pg_lease,
    renew_pg_lease,
)
from littera.domain.guards import GuardViolation
from littera.tui import actions, keymap, queries
from littera.tui.decorators import safe_action
from littera.tui.state import (
    AlignmentsClearSelection,
    AlignmentsSelect,
    AppState,
    ClearDetail,
    ClearSelection,
    EditTarget,
    EntitiesClearSelection,
    EntitiesSelect,
    ExitEditor,
    GotoAlignments,
    GotoEntities,
    GotoOutline,
    GotoReviews,
    OutlinePop,
    OutlinePush,
    OutlineSelect,
    PathElement,
    ReviewsSelect,
    SetDetail,
    StartEdit,
)
from littera.tui.views.alignments import AlignmentsView
from littera.tui.views.editor import EditorView
from littera.tui.views.entities import EntitiesView
from littera.tui.views.input_dialog import (
    ConfirmDialog,
    HelpDialog,
    InputDialog,
    PickListDialog,
    RecoveryDialog,
    SnapshotConfirmDialog,
)
from littera.tui.views.outline import OutlineView
from littera.tui.views.reviews import ReviewsView

logger = logging.getLogger(__name__)


class _DbFailure:
    """Sentinel returned by :meth:`LitteraApp._db` when a call did not succeed.

    It is falsy so that ``if not result:`` reads naturally, and distinct from
    ``None`` so that a function which legitimately returns ``None`` is not
    mistaken for a failure.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "DB_FAILED"


DB_FAILED = _DbFailure()


_DEPENDENT_NOUNS = (
    ("sections", "section", "sections"),
    ("blocks", "block", "blocks"),
    ("mentions", "mention", "mentions"),
    ("alignments", "alignment", "alignments"),
)


def _mention_options(mentions: list[tuple]) -> list[tuple[str, str]]:
    """PickListDialog options keyed by mention_id.

    Mentions used to be addressed by 1-based index into a list snapshotted at
    prompt time, so a concurrent write deleted the wrong one. The id is the
    only stable handle.
    """
    options = []
    for mention_id, entity_type, label, language, surface in mentions:
        text = f"{entity_type}: {label} ({language})"
        if surface:
            text += f' surface: "{surface}"'
        options.append((mention_id, text))
    return options


ALIGNMENT_TYPES = ("translation", "adaptation", "summary")

# Least to most urgent, not alphabetical.
_SEVERITY_ORDER = tuple(
    s for s in ("low", "medium", "high") if s in VALID_SEVERITIES
) or tuple(sorted(VALID_SEVERITIES))


def _severity_options(current: str | None = None) -> list[tuple[str, str]]:
    """PickListDialog options for a review's severity.

    A typo in a free-text severity prompt used to throw away the long
    description the writer had just typed.
    """
    options = []
    for severity in _SEVERITY_ORDER:
        label = severity
        if current and severity == current:
            label = f"{severity} (current)"
        options.append((severity, label))
    return options


def describe_delete_dependents(counts: dict) -> str:
    """Confirm-dialog text naming what a delete takes with it.

    Cascades in db/schema.sql are silent; "This cannot be undone." alone does
    not tell a writer that three mentions and an alignment go with the block.
    """
    parts = []
    for key, singular, plural in _DEPENDENT_NOUNS:
        count = counts.get(key, 0) if counts else 0
        if count:
            parts.append(f"{count} {singular if count == 1 else plural}")

    lines = ["This cannot be undone."]
    if parts:
        lines.append("Also deleted: " + ", ".join(parts) + ".")
    reviews = counts.get("reviews", 0) if counts else 0
    if reviews:
        noun = "review" if reviews == 1 else "reviews"
        lines.append(f"{reviews} {noun} scoped here will be kept, but unscoped.")
    return "\n".join(lines)


class LitteraApp(App):
    TITLE = "Littera"
    CSS_PATH = "tui.css"
    # One list, in keymap.py, feeds the footer, the hint bars and the help
    # overlay. Do not hand-write a second copy anywhere.
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = list(keymap.BINDINGS)

    # True while a worker thread holds the shared DB connection.
    _io_busy = False

    def check_action(self, action: str, parameters) -> bool:
        """Hide (and disable) keys that would do nothing in this state.

        In Textual 7, False means "disabled and not shown": the footer stops
        advertising all 28 keys in every view, and a key that is advertised
        always does something. (None would grey it out but keep it listed.)
        """
        return keymap.is_available(getattr(self, "state", None), action)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state: AppState | None = None
        self.views = {}
        self._pg_cfg = None
        self._pg_started_here = False
        self._work_cfg: dict = {}
        self._littera_dir: Path | None = None
        self._lease_seconds = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(id="main")
        yield Static("", id="word-count-bar")
        yield Footer()

    def on_mount(self) -> None:
        littera_dir = Path.cwd() / ".littera"
        if not littera_dir.exists():
            # A blank screen with 31 keys that silently do nothing is worse
            # than an honest exit.
            self.exit(
                return_code=1,
                message="Not a Littera work — run 'littera init <name>' first.",
            )
            return

        self._littera_dir = littera_dir

        logging.basicConfig(
            filename=littera_dir / "tui.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        self._show_boot_message("Starting the embedded database…")

        # Paint one frame before blocking: starting Postgres can take seconds
        # and the user would otherwise stare at an empty screen.
        self.call_after_refresh(self._boot)

    def _show_boot_message(self, text: str) -> None:
        """Put a single line in the main pane while the app is still booting."""
        try:
            container = self.screen.query_one("#main")
        except NoMatches:
            return
        try:
            container.mount(Static(text, id="boot-message"))
        except Exception:  # pragma: no cover - cosmetic only
            logger.debug("could not mount boot message", exc_info=True)

    def _boot(self) -> None:
        """Start Postgres and open the work. Any failure exits with a message."""
        littera_dir = self._littera_dir
        if littera_dir is None:
            return

        try:
            self._work_cfg = self._load_cfg()
            EmbeddedPostgresManager(littera_dir).ensure()
            pg_cfg = postgres_config_from_work(littera_dir, self._work_cfg)
            self._pg_cfg = pg_cfg
        except Exception as e:  # noqa: BLE001 - boot boundary: convert any startup failure into a readable exit
            self._fail_boot("Could not read this Littera work", e)
            return

        try:
            self._pg_started_here = start_postgres(pg_cfg)
        except WalCorruptionError as e:
            can_recover = find_pg_resetwal(pg_cfg) is not None
            self._handle_wal_corruption(pg_cfg, e, can_recover)
            return
        except Exception as e:  # noqa: BLE001 - boot boundary: convert any startup failure into a readable exit
            self._fail_boot("Could not start the embedded database", e)
            return

        try:
            self._finish_init(pg_cfg, self._work_cfg)
        except Exception as e:  # noqa: BLE001 - boot boundary: convert any startup failure into a readable exit
            self._fail_boot("Could not open the work database", e)

    def _fail_boot(self, title: str, error: Exception) -> None:
        """Exit with a readable message instead of a raw traceback."""
        logger.error("%s: %s", title, error, exc_info=error)
        self.exit(
            return_code=1,
            message=f"{title}\n\n{type(error).__name__}: {error}",
        )

    def _finish_init(self, pg_cfg, cfg: dict) -> None:
        """Complete TUI initialization after PG is running."""
        # Take the lease before touching the database: a CLI command's lease
        # watcher could otherwise stop Postgres in the middle of migrate().
        self._take_pg_lease()
        conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)

        # The TUI is a first-class interface: it must not assume that some CLI
        # command already brought the schema up to date.
        migrate(conn)

        self.state = AppState(work=cfg, db=conn)
        self.views = {
            "outline": OutlineView(),
            "entities": EntitiesView(),
            "alignments": AlignmentsView(),
            "editor": EditorView(),
            "reviews": ReviewsView(),
        }
        try:
            self.screen.query_one("#boot-message").remove()
        except NoMatches:
            pass
        self._render_view()

    # =====================
    # Postgres lease
    # =====================

    def _take_pg_lease(self) -> None:
        """Keep the Postgres lease alive for as long as the TUI runs.

        A CLI command may have started Postgres with a short lease and spawned
        a watcher (`littera.db.pg_lease`) that runs `pg_ctl stop -m fast` once
        it expires. Without renewing, that watcher would kill the connection
        underneath a live editing session.
        """
        littera_dir = self._littera_dir
        if littera_dir is None:
            return

        seconds = pg_lease_seconds()
        if seconds <= 0:
            # Leases are disabled (tests, or LITTERA_PG_LEASE_SECONDS=0), so
            # no watcher exists to renew against.
            return

        self._lease_seconds = seconds
        self._renew_pg_lease()
        # Renew well before expiry; the watcher wakes at most every 5s.
        self.set_interval(max(seconds / 3.0, 1.0), self._renew_pg_lease)

    def _renew_pg_lease(self) -> None:
        littera_dir = self._littera_dir
        if littera_dir is None or self._lease_seconds <= 0:
            return
        try:
            renew_pg_lease(littera_dir, self._lease_seconds)
        except OSError:
            logger.warning("could not renew the Postgres lease", exc_info=True)

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
                self._confirm_reinit(pg_cfg)
            else:
                self.exit()

        self.push_screen(RecoveryDialog(message, can_recover), on_choice)

    def _confirm_reinit(self, pg_cfg) -> None:
        """Ask a second time before destroying the work's data."""

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._attempt_reinit(pg_cfg)
            else:
                self.exit()

        self.push_screen(
            ConfirmDialog(
                "Erase this work's database?",
                "Re-initializing deletes every document, section, block, "
                "entity, mention and review in this work. This cannot be undone.",
            ),
            on_confirm,
        )

    def _attempt_wal_recovery(self, pg_cfg) -> None:
        """Run pg_resetwal, restart PG, and continue init."""
        try:
            reset_wal(pg_cfg)
            self._pg_started_here = start_postgres(pg_cfg)
            self._finish_init(pg_cfg, self._work_cfg)
        except Exception as e:
            logger.exception("WAL recovery failed")
            self.notify(f"Recovery failed: {e}", severity="error")
            self.exit()

    def _attempt_reinit(self, pg_cfg) -> None:
        """Delete pgdata, reinit, recreate DB + schema, continue init."""
        try:
            reinit_cluster(pg_cfg)
            self._pg_started_here = start_postgres(pg_cfg)
            ensure_database(pg_cfg)
            self._finish_init(pg_cfg, self._work_cfg)
        except Exception as e:
            logger.exception("Re-initialization failed")
            self.notify(f"Re-initialization failed: {e}", severity="error")
            self.exit()

    def on_unmount(self) -> None:
        if self.state is not None:
            self.state.db.close()

        littera_dir = getattr(self, "_littera_dir", None)
        started_here = getattr(self, "_pg_started_here", False)

        if started_here and getattr(self, "_pg_cfg", None) is not None:
            # We own the cluster: drop the lease first so a watcher spawned by
            # some CLI command does not try to stop it again.
            if littera_dir is not None:
                release_pg_lease(littera_dir)
            stop_postgres(self._pg_cfg)
        elif littera_dir is not None and self._lease_seconds > 0:
            # Someone else started Postgres. Hand the lease back at its normal
            # length so their watcher shuts it down as usual.
            self._renew_pg_lease()

    # =====================
    # View switching
    # =====================

    def _switch_view(self, goto_action) -> None:
        """Leave the editor (asking first if it is dirty), then switch view.

        ExitEditor is dispatched *before* the Goto action: ExitEditor restores
        `view` from the editor overlay's return_to, so the other order left
        `view` and `active_base` disagreeing.
        """
        if self.state is None:
            return

        def go() -> None:
            self.state.dispatch(ExitEditor())
            self.state.dispatch(goto_action)
            self._render_view()

        if self.state.view == "editor":
            self._confirm_discard(go)
            return
        go()

    def action_outline(self) -> None:
        self._switch_view(GotoOutline())

    def action_entities(self) -> None:
        self._switch_view(GotoEntities())

    def action_alignments(self) -> None:
        self._switch_view(GotoAlignments())

    def action_reviews(self) -> None:
        self._switch_view(GotoReviews())

    def action_quit(self) -> None:
        """Quit, but never throw away unsaved editor text without asking."""
        if self.state is not None and self.state.view == "editor":
            self._confirm_discard(self.exit)
            return
        self.exit()

    # =====================
    # Navigation
    # =====================

    @safe_action
    def action_enter(self) -> None:
        """Open the selected row: drill down, or edit what it stands for."""
        if self.state is None:
            return

        # Every list view promised "Enter" in the footer; only the outline
        # honoured it. Give the other three a meaning instead of a no-op.
        if self.state.view == "entities":
            self.action_edit_note()
            return
        if self.state.view == "reviews":
            self._prompt_edit_review()
            return
        if self.state.view == "alignments":
            self.notify("Alignments have no sub-level — d deletes, g finds gaps")
            return

        if self.state.view != "outline":
            return
        if not self.state.entity_selection.id:
            return

        sel = self.state.entity_selection

        if sel.kind in ("document", "section"):
            title = self._db(
                queries.fetch_item_title, self.state.db, sel.kind, sel.id,
                label="Read title",
            )
            if title is DB_FAILED:
                return
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

        # The list always auto-highlights a row, so "clear the selection first"
        # made Esc a no-op forever. The hint bars promise "Esc:back": honour it.
        if self.state.view in ("entities", "alignments", "reviews"):
            self.action_outline()
            return

        # Outline view: pop path
        if self.state.outline.path:
            self.state.dispatch(OutlinePop())
            self._render_view()

    # =====================
    # Reordering
    # =====================

    @safe_action
    def action_move_up(self) -> None:
        """Move selected document, section, or block up by one position."""
        self._move_selected(-1)

    @safe_action
    def action_move_down(self) -> None:
        """Move selected document, section, or block down by one position."""
        self._move_selected(+1)

    def _move_selected(self, direction: int) -> None:
        """Move the selected item up (-1) or down (+1)."""
        if self.state is None or self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if not sel.id or sel.kind not in ("document", "section", "block"):
            return

        # Find current position among siblings
        items = self.state.outline.items
        current_idx = None
        for i, item in enumerate(items):
            if item.id == sel.id:
                current_idx = i
                break
        if current_idx is None:
            return

        new_position = current_idx + 1 + direction  # 1-based
        if new_position < 1:
            self.notify(f"Already the first {sel.kind}")
            return
        if new_position > len(items):
            self.notify(f"Already the last {sel.kind}")
            return

        moved = self._db(
            actions.move_item, self.state.db, sel.kind, sel.id, new_position,
            label="Move item",
        )
        if moved is DB_FAILED:
            return
        if not moved:
            # move_item returns False when the row (or its parent) is gone.
            self.notify("Could not move this item", severity="warning")
            return
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

        if self.state.view == "alignments":
            self._prompt_add_alignment()
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

        def on_type_result(entity_type: str) -> None:
            async def on_name_result(name: str | None) -> None:
                if not name:
                    return
                self._create_entity(entity_type, name)

            self.push_screen(
                InputDialog("New Entity", "Name:", ""),
                on_name_result,
            )

        self._prompt_entity_type(
            "New Entity", "Type (e.g. concept):", on_type_result
        )

    @safe_action
    def _create_entity(self, entity_type: str, name: str) -> None:
        if self.state is None:
            return
        entity_id = self._db(
            actions.create_entity, self.state.db, entity_type, name,
            label="Create entity",
        )
        if entity_id is DB_FAILED or entity_id is None:
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
        doc_id = self._db(
            actions.create_document, self.state.db, work_id, title,
            label="Create document",
        )
        if doc_id is DB_FAILED:
            return
        self.state.dispatch(OutlineSelect(kind="document", item_id=doc_id))
        self._render_view()

    @safe_action
    def _create_section(self, title: str) -> None:
        if self.state is None:
            return
        doc = self.state.current_document
        if not doc:
            return
        section_id = self._db(
            actions.create_section, self.state.db, doc.id, title,
            label="Create section",
        )
        if section_id is DB_FAILED:
            return
        self.state.dispatch(OutlineSelect(kind="section", item_id=section_id))
        self._render_view()

    @safe_action
    def _create_block(self) -> None:
        if self.state is None:
            return
        section = self.state.current_section
        if not section:
            return
        block_id = self._db(
            actions.create_block, self.state.db, section.id,
            label="Create block",
        )
        if block_id is DB_FAILED:
            return
        self.state.dispatch(OutlineSelect(kind="block", item_id=block_id))
        self._render_view()
        # The block is created empty, so drop straight into the editor: an
        # empty row the writer has to find and open again is worse than the
        # placeholder text it replaces.
        self.action_edit_block()

    def _prompt_entity_type(self, title: str, prompt: str, on_type) -> None:
        """Pick an entity type from the ones already in use, or type a new one.

        A free-text prompt made "concept" and "Concept" two different types
        and gave no clue what the work already uses.
        """
        known = self._db(
            queries.list_entity_types, self.state.db, label="List entity types"
        )
        if known is DB_FAILED:
            known = []
        options = [(t, t) for t in known]
        options.append(("__other__", "Another type…"))

        async def on_pick(choice: str | None) -> None:
            if not choice:
                return
            if choice != "__other__":
                on_type(choice)
                return

            async def on_typed(value: str | None) -> None:
                value = (value or "").strip()
                if value:
                    on_type(value)

            self.push_screen(InputDialog(title, prompt, ""), on_typed)

        self.push_screen(PickListDialog(title, options), on_pick)

    def _scope_candidate(self) -> tuple[str, str] | None:
        """(scope, scope_id) for whatever the writer currently has selected.

        Reviews are added from the reviews view, but the outline and entity
        selections persist across that hop — which is exactly the thing the
        writer was looking at when they decided to leave a note about it.
        """
        if self.state is None:
            return None

        if self.state.view == "alignments":
            sel = self.state.alignments.selection
            if sel.kind == "alignment" and sel.id:
                return "alignment", sel.id

        sel = self.state.outline.selection
        if sel.kind in ("document", "section", "block") and sel.id:
            return sel.kind, sel.id

        sel = self.state.entities.selection
        if sel.kind == "entity" and sel.id:
            return "entity", sel.id

        return None

    def _scope_options(self, include_unchanged: bool = False) -> list[tuple[str, str]]:
        """PickListDialog options for choosing a review's scope."""
        options: list[tuple[str, str]] = []
        if include_unchanged:
            options.append(("unchanged", "Leave the scope as it is"))

        candidate = self._scope_candidate()
        if candidate:
            scope, scope_id = candidate
            label = self._db(
                queries.fetch_scope_label, self.state.db, scope, scope_id,
                label="Read scope target",
            )
            if label is DB_FAILED:
                label = None
            suffix = f" — {label}" if label else ""
            options.append((f"sel:{scope}:{scope_id}", f"This {scope}{suffix}"))

        options.append(("work", "The whole work"))
        options.append(("none", "No scope" if not include_unchanged else "Clear the scope"))
        return options

    def _resolve_scope_choice(self, choice: str) -> tuple[str | None, str | None]:
        """Turn a picker option id into (scope, scope_id)."""
        if choice == "work":
            work_id = (self.state.work or {}).get("work", {}).get("id")
            return ("work", str(work_id)) if work_id else (None, None)
        if choice.startswith("sel:"):
            _, scope, scope_id = choice.split(":", 2)
            return scope, scope_id
        return None, None

    @safe_action
    def _prompt_add_review(self) -> None:
        """Chain dialogs to create a review: description, severity, scope, type."""
        # Captured before the dialogs open: pushing screens can move focus,
        # and the scope must mean "what I was looking at when I pressed a".
        options = self._scope_options()

        async def on_desc_result(description: str | None) -> None:
            if description is None:
                return
            description = description.strip()
            if not description:
                self.notify("Description cannot be empty", severity="warning")
                return

            async def on_severity_result(severity: str | None) -> None:
                if not severity:
                    return

                async def on_scope_result(choice: str | None) -> None:
                    if choice is None:
                        return
                    scope, scope_id = self._resolve_scope_choice(choice)

                    async def on_type_result(issue_type: str | None) -> None:
                        self._create_review(
                            description,
                            severity,
                            scope,
                            scope_id,
                            (issue_type or "").strip() or None,
                        )

                    self.push_screen(
                        InputDialog("New Review", "Issue type (optional):", ""),
                        on_type_result,
                    )

                self.push_screen(
                    PickListDialog("Scope this review", options),
                    on_scope_result,
                )

            self.push_screen(
                PickListDialog("Severity", _severity_options()),
                on_severity_result,
            )

        self.push_screen(
            InputDialog("New Review", "Description:", ""),
            on_desc_result,
        )

    @safe_action
    def _create_review(
        self,
        description: str,
        severity: str,
        scope: str | None = None,
        scope_id: str | None = None,
        issue_type: str | None = None,
    ) -> None:
        if self.state is None or self.state.work is None:
            return
        work_id = self.state.work.get("work", {}).get("id")
        if work_id is None:
            return
        review_id = self._db(
            actions.create_review, self.state.db, work_id, description, severity,
            scope, issue_type, scope_id,
            label="Create review",
        )
        if review_id is DB_FAILED:
            return
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
            if self._db(
                actions.delete_review, self.state.db, review_id,
                label="Delete review",
            ) is DB_FAILED:
                return
            self.state.dispatch(ClearSelection())
            self._render_view()

        self.push_screen(
            ConfirmDialog("Delete Review?", "This cannot be undone."),
            on_confirm,
        )

    @safe_action
    def _prompt_edit_review(self) -> None:
        """Chain dialogs to edit the selected review: description then severity."""
        if self.state is None:
            return
        sel = self.state.reviews.selection
        if not sel or sel.kind != "review" or not sel.id:
            return

        review_id = sel.id
        fetched = self._db(
            queries.fetch_review, self.state.db, review_id, label="Read review"
        )
        if fetched is DB_FAILED:
            return
        current_desc, current_severity = fetched

        async def on_desc_result(description: str | None) -> None:
            if description is None:
                return
            description = description.strip()
            if not description:
                self.notify("Description cannot be empty", severity="warning")
                return

            async def on_severity_result(severity: str | None) -> None:
                if not severity:
                    return

                async def on_scope_result(choice: str | None) -> None:
                    if choice is None:
                        return
                    scope: str | None = None
                    scope_id: str | None = None
                    clear_scope = False
                    if choice == "none":
                        clear_scope = True
                    elif choice != "unchanged":
                        scope, scope_id = self._resolve_scope_choice(choice)

                    if self._db(
                        actions.update_review,
                        self.state.db,
                        review_id,
                        description=description,
                        severity=severity,
                        scope=scope,
                        scope_id=scope_id,
                        clear_scope=clear_scope,
                        label="Update review",
                    ) is DB_FAILED:
                        return
                    self._render_view()

                self.push_screen(
                    PickListDialog(
                        "Scope this review", self._scope_options(include_unchanged=True)
                    ),
                    on_scope_result,
                )

            self.push_screen(
                PickListDialog("Severity", _severity_options(current_severity)),
                on_severity_result,
            )

        self.push_screen(
            InputDialog("Edit Review", "Description:", current_desc),
            on_desc_result,
        )

    @safe_action
    def action_edit_title(self) -> None:
        """Edit title of selected document or section, or edit a review."""
        if self.state is None:
            return
        if self.state.view == "reviews":
            self._prompt_edit_review()
            return
        if self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if sel.kind == "block":
            self.notify(
                "Blocks have no title — press Enter to edit the text",
                severity="warning",
            )
            return
        if sel.kind not in ("document", "section") or not sel.id:
            return

        current_title = self._db(
            queries.fetch_item_title, self.state.db, sel.kind, sel.id,
            label="Read title",
        )
        if current_title is DB_FAILED:
            return
        kind_label = sel.kind.title()
        kind = sel.kind
        item_id = sel.id

        async def on_title_result(title: str | None) -> None:
            if title is None:
                return
            if self._db(
                actions.update_title, self.state.db, kind, item_id, title,
                label="Rename",
            ) is DB_FAILED:
                return
            self._render_view()

        self.push_screen(
            InputDialog(f"Edit {kind_label}", "New title:", current_title or ""),
            on_title_result,
        )

    @safe_action
    def action_set_language(self) -> None:
        """Set the language of the selected block."""
        if self.state is None or self.state.view != "outline":
            return

        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        block_id = sel.id
        fetched = self._db(
            queries.fetch_block_text, self.state.db, block_id, label="Read block"
        )
        if fetched is DB_FAILED:
            return
        current_lang = fetched[0]

        async def on_lang_result(language: str | None) -> None:
            if not language:
                return
            if self._db(
                actions.set_block_language, self.state.db, block_id, language,
                label="Set language",
            ) is DB_FAILED:
                return
            self._render_view()

        self.push_screen(
            InputDialog("Set Language", "Language:", current_lang),
            on_lang_result,
        )

    @safe_action
    def action_delete_item(self) -> None:
        """Delete selected document/section/block, entity, alignment, or review."""
        if self.state is None:
            return
        if self.state.view == "alignments":
            self.action_delete_alignment()
            return
        if self.state.view == "reviews":
            self._delete_review()
            return
        if self.state.view == "entities":
            self._delete_entity()
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

        counts = self._db(
            actions.count_delete_dependents, self.state.db, kind, item_id,
            label="Count dependents",
        )
        if counts is DB_FAILED:
            return

        async def on_choice(choice: str) -> None:
            if choice not in ("confirm", "snapshot"):
                return
            if choice == "snapshot" and not self._write_snapshot_now(f"before-delete-{kind}"):
                return
            if self._db(
                actions.delete_item, self.state.db, kind, item_id, label="Delete"
            ) is DB_FAILED:
                return
            self.state.dispatch(ClearSelection())
            self._render_view()

        self.push_screen(
            SnapshotConfirmDialog(
                f"Delete {kind_label}?", describe_delete_dependents(counts)
            ),
            on_choice,
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
            if not name or not name.strip():
                return
            name = name.strip()
            matches = self._db(
                actions.find_entities_by_label, self.state.db, name,
                label="Find entity",
            )
            if matches is DB_FAILED:
                return
            self._pick_entity_to_link(block_id, name, matches)

        self.push_screen(
            InputDialog("Link to Entity", "Entity Name:", ""), on_name_result
        )

    def _pick_entity_to_link(
        self, block_id: str, name: str, matches: list[tuple[str, str, str]]
    ) -> None:
        """Choose which entity to bind, or say explicitly to create one.

        Entities are never created as a side effect of linking: INVARIANTS.md
        forbids auto-creating entities without intent, and the label alone is
        ambiguous when two entity types share it.
        """
        options = [
            (entity_id, f"{entity_type}: {label}")
            for entity_id, entity_type, label in matches
        ]
        options.append(("__new__", f"Create new entity “{name}”…"))

        title = (
            f"Link to “{name}”"
            if matches
            else f"No entity named “{name}”"
        )

        async def on_pick(choice: str | None) -> None:
            if choice is None:
                return
            if choice == "__new__":
                self._prompt_create_entity_then_link(block_id, name)
                return
            self._link_block_to_entity(block_id, choice)

        self.push_screen(PickListDialog(title, options), on_pick)

    def _prompt_create_entity_then_link(self, block_id: str, name: str) -> None:
        """Ask for the entity type, create it, then link the block to it."""

        def on_type_result(entity_type: str) -> None:
            entity_id = self._db(
                actions.create_entity, self.state.db, entity_type, name,
                label="Create entity",
            )
            if entity_id is DB_FAILED or not entity_id:
                return
            self._link_block_to_entity(
                block_id, entity_id, created=f"{entity_type} {name}"
            )

        self._prompt_entity_type(
            "New Entity", f"Type for “{name}” (e.g. concept):", on_type_result
        )

    def _link_block_to_entity(
        self, block_id: str, entity_id: str, created: str | None = None
    ) -> None:
        linked = self._db(
            actions.link_block_to_entity, self.state.db, block_id, entity_id,
            label="Link entity",
        )
        if linked is DB_FAILED:
            return
        if created:
            self.notify(f"Created {created} and linked it to this block")
        elif linked:
            self.notify("Linked to this block")
        else:
            self.notify("Already linked to this block")
        self._render_view()

    @safe_action
    def _delete_entity(self) -> None:
        """Delete the selected entity with confirmation."""
        if self.state is None or self.state.view != "entities":
            return
        sel = self.state.entities.selection
        if sel.kind != "entity" or not sel.id:
            return

        entity_id = sel.id

        async def on_choice(choice: str) -> None:
            if choice not in ("confirm", "snapshot"):
                return
            if choice == "snapshot" and not self._write_snapshot_now("before-delete-entity"):
                return
            if self._db(
                actions.delete_entity, self.state.db, entity_id,
                label="Delete entity",
            ) is DB_FAILED:
                return
            self.state.dispatch(EntitiesClearSelection())
            self._render_view()

        self.push_screen(
            SnapshotConfirmDialog(
                "Delete Entity?",
                "This will also delete all mentions and labels for this entity.",
            ),
            on_choice,
        )

    # =====================
    # Entity labels & properties
    # =====================

    def _selected_entity_id(self) -> str | None:
        """The entity the writer is looking at, or None."""
        if self.state is None or self.state.view != "entities":
            return None
        sel = self.state.entity_selection
        if sel.kind != "entity" or not sel.id:
            return None
        return sel.id

    @safe_action
    def action_entity_labels(self) -> None:
        """Add or delete a label on the selected entity.

        One reachable key with a picker, instead of L to add and
        ctrl+shift+l to delete: Textual has no ctrl+shift+letter sequence in
        most terminals, so the delete half collapsed onto ctrl+l and deleting
        a label was impossible with no feedback at all.
        """
        entity_id = self._selected_entity_id()
        if entity_id is None:
            return

        labels = self._db(
            queries.fetch_entity_labels, self.state.db, entity_id,
            label="Read labels",
        )
        if labels is DB_FAILED:
            return

        options: list[tuple[str, str]] = [("__add__", "Add a label…")]
        options += [
            (f"del:{language}", f"Delete {language}: {base_form}")
            for language, base_form in labels
        ]

        async def on_pick(choice: str | None) -> None:
            if not choice:
                return
            if choice == "__add__":
                self._prompt_add_label(entity_id)
                return
            self._delete_label(entity_id, choice.split(":", 1)[1])

        self.push_screen(PickListDialog("Labels", options), on_pick)

    @safe_action
    def _prompt_add_label(self, entity_id: str) -> None:
        """Ask for a language and a base form, then add the label."""

        async def on_lang_result(language: str | None) -> None:
            if not language:
                return

            async def on_form_result(base_form: str | None) -> None:
                if not base_form:
                    return
                if self._db(
                    actions.add_entity_label,
                    self.state.db, entity_id, language, base_form,
                    label="Add label",
                ) is DB_FAILED:
                    return
                self.notify(f"Label added ({language})")
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
    def _delete_label(self, entity_id: str, language: str) -> None:
        deleted = self._db(
            actions.delete_entity_label, self.state.db, entity_id, language,
            label="Delete label",
        )
        if deleted is DB_FAILED:
            return
        if deleted:
            self.notify(f"Label deleted ({language})")
        else:
            self.notify(f"No {language} label found", severity="warning")
        self._render_view()

    @safe_action
    def action_entity_properties(self) -> None:
        """Set or delete a property on the selected entity (one picker)."""
        entity_id = self._selected_entity_id()
        if entity_id is None:
            return

        properties = self._db(
            queries.fetch_entity_properties, self.state.db, entity_id,
            label="Read properties",
        )
        if properties is DB_FAILED:
            return

        options: list[tuple[str, str]] = [("__set__", "Set a property…")]
        options += [
            (f"del:{key}", f"Delete {key} = {value}")
            for key, value in sorted(properties.items())
        ]

        async def on_pick(choice: str | None) -> None:
            if not choice:
                return
            if choice == "__set__":
                self._prompt_set_property(entity_id)
                return
            self._delete_property(entity_id, choice.split(":", 1)[1])

        self.push_screen(PickListDialog("Properties", options), on_pick)

    @safe_action
    def _prompt_set_property(self, entity_id: str) -> None:
        async def on_kv_result(kv: str | None) -> None:
            if not kv or "=" not in kv:
                if kv:
                    self.notify("Format: key=value", severity="warning")
                return
            key, value = kv.split("=", 1)
            if self._db(
                actions.set_entity_property, self.state.db, entity_id, key, value,
                label="Set property",
            ) is DB_FAILED:
                return
            self.notify(f"Property set: {key}={value}")
            self._render_view()

        self.push_screen(
            InputDialog("Set Property", "key=value:", ""),
            on_kv_result,
        )

    @safe_action
    def _delete_property(self, entity_id: str, key: str) -> None:
        deleted = self._db(
            actions.delete_entity_property, self.state.db, entity_id, key,
            label="Delete property",
        )
        if deleted is DB_FAILED:
            return
        if deleted:
            self.notify(f"Property deleted: {key}")
        else:
            self.notify(f"Property '{key}' not found", severity="warning")
        self._render_view()

    # =====================
    # Alignment management
    # =====================

    @safe_action
    def _prompt_add_alignment(self) -> None:
        """Pick source/target blocks by preview, then alignment type."""
        if self.state is None:
            return
        options = self._db(
            queries.list_blocks_for_picker, self.state.db, label="List blocks"
        )
        if options is DB_FAILED:
            return
        if len(options) < 2:
            self.notify("Need at least two blocks to create an alignment", severity="warning")
            return

        async def on_src_result(src_id: str | None) -> None:
            if not src_id:
                return
            remaining = [(oid, label) for oid, label in options if oid != src_id]

            async def on_tgt_result(tgt_id: str | None) -> None:
                if not tgt_id:
                    return

                async def on_type_result(atype: str | None) -> None:
                    if not atype:
                        return
                    self._create_alignment(src_id, tgt_id, atype)

                self.push_screen(
                    PickListDialog(
                        "Alignment type",
                        [(t, t) for t in ALIGNMENT_TYPES],
                    ),
                    on_type_result,
                )

            self.push_screen(
                PickListDialog("Align — target block", remaining),
                on_tgt_result,
            )

        self.push_screen(
            PickListDialog("Align — source block", options),
            on_src_result,
        )

    @safe_action
    def action_show_help(self) -> None:
        """Show model + shortcut cheatsheet."""
        self.push_screen(HelpDialog(keymap.help_text(self.state)))

    @safe_action
    def _create_alignment(self, src_id: str, tgt_id: str, atype: str) -> None:
        if self.state is None:
            return
        result = self._db(
            actions.create_alignment, self.state.db, src_id, tgt_id, atype,
            label="Create alignment",
        )
        if result is DB_FAILED:
            return
        if result is None:
            self.notify("Alignment already exists between these blocks", severity="warning")
            return
        self.state.dispatch(AlignmentsSelect(result))
        self._render_view()

    @safe_action
    def action_delete_alignment(self) -> None:
        """Delete the selected alignment."""
        if self.state is None or self.state.view != "alignments":
            return
        sel = self.state.alignments.selection
        if sel.kind != "alignment" or not sel.id:
            return

        alignment_id = sel.id

        async def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            if self._db(
                actions.delete_alignment, self.state.db, alignment_id,
                label="Delete alignment",
            ) is DB_FAILED:
                return
            self.state.dispatch(AlignmentsClearSelection())
            self._render_view()

        self.push_screen(
            ConfirmDialog("Delete Alignment?", "This cannot be undone."),
            on_confirm,
        )

    @safe_action
    def action_show_gaps(self) -> None:
        """Show gap detection results in the detail panel."""
        if self.state is None or self.state.view != "alignments":
            return

        db = self.state.db

        asked_from = self.state.view

        def show(gaps_text: str) -> None:
            # Gap detection scans every alignment; if the user moved on while
            # it ran, the result belongs to the view that asked for it.
            if self.state is None or self.state.view != asked_from:
                return
            self.state.dispatch(SetDetail(gaps_text))
            self._refresh_detail()

        self._run_io(
            "Checking alignments for gaps…",
            lambda: queries.fetch_alignment_gaps(db),
            show,
            "Gap detection failed",
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

        mentions = self._db(
            queries.fetch_block_mentions, self.state.db, sel.id,
            label="Read mentions",
        )
        if mentions is DB_FAILED:
            return
        if not mentions:
            self.notify("No mentions for this block")
            return

        lines = ["Mentions for this block:", ""]
        for i, (mid, etype, elabel, lang, sform) in enumerate(mentions, 1):
            line = f"  {i}. {etype} {elabel} ({lang})"
            if sform:
                line += f' surface: "{sform}"'
            lines.append(line)
        lines.append("")
        lines.append("S: set surface   D: delete mention")

        self.state.dispatch(SetDetail("\n".join(lines)))
        self._refresh_detail()

    @safe_action
    def action_delete_mention(self) -> None:
        """Delete a mention from the selected block by number."""
        if self.state is None or self.state.view != "outline":
            return
        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        block_id = sel.id
        mentions = self._db(
            queries.fetch_block_mentions, self.state.db, block_id,
            label="Read mentions",
        )
        if mentions is DB_FAILED:
            return
        if not mentions:
            self.notify("No mentions to delete")
            return

        async def on_pick(mention_id: str | None) -> None:
            if not mention_id:
                return
            if self._db(
                actions.delete_mention, self.state.db, mention_id,
                label="Delete mention",
            ) is DB_FAILED:
                return
            self.notify("Mention deleted")
            self._render_view()

        self.push_screen(
            PickListDialog("Delete Mention", _mention_options(mentions)),
            on_pick,
        )

    @safe_action
    def action_set_surface(self) -> None:
        """Set surface form on a mention in the selected block."""
        if self.state is None or self.state.view != "outline":
            return
        sel = self.state.entity_selection
        if sel.kind != "block" or not sel.id:
            return

        block_id = sel.id
        mentions = self._db(
            queries.fetch_block_mentions, self.state.db, block_id,
            label="Read mentions",
        )
        if mentions is DB_FAILED:
            return
        if not mentions:
            self.notify("No mentions for this block")
            return

        by_id = {m[0]: m for m in mentions}

        async def on_pick(mention_id: str | None) -> None:
            if not mention_id or mention_id not in by_id:
                return
            language = by_id[mention_id][3]

            async def on_features_result(features_str: str | None) -> None:
                if not features_str:
                    return
                self._apply_surface_form(mention_id, language, features_str)

            self.push_screen(
                InputDialog("Set Surface", "Features (e.g. plural, case=gen):", ""),
                on_features_result,
            )

        self.push_screen(
            PickListDialog("Set Surface", _mention_options(mentions)),
            on_pick,
        )

    @safe_action
    def _apply_surface_form(self, mention_id: str, language: str, features_str: str) -> None:
        """Parse features, compute surface form, and update mention."""
        # Parse features string
        features: dict = {}
        for token in features_str.split(","):
            token = token.strip()
            if not token:
                continue
            if token == "plural":
                features["number"] = "pl"
            elif token == "possessive":
                features["case"] = "poss"
            elif "=" in token:
                key, value = token.split("=", 1)
                features[key.strip()] = value.strip()

        try:
            self._apply_surface_form_sql(mention_id, language, features)
        except psycopg.Error as exc:
            self._db_failed("Set surface form", exc)
            return
        self._render_view()

    def _apply_surface_form_sql(self, mention_id: str, language: str, features: dict) -> None:
        """Compute and store a mention's surface form. Raises on DB failure."""
        import json

        from littera.linguistics.dispatch import surface_form as dispatch_surface_form

        with self.state.db.cursor() as cur:
            # Get entity_id for this mention
            cur.execute(
                "SELECT entity_id FROM mentions WHERE id = %s",
                (mention_id,),
            )
            row = cur.fetchone()
            if row is None:
                self.notify("That mention no longer exists", severity="warning")
                return
            entity_id = row[0]

            # Look up base_form from entity_labels for this language
            cur.execute(
                "SELECT base_form FROM entity_labels WHERE entity_id = %s AND language = %s",
                (entity_id, language),
            )
            row = cur.fetchone()
            if row:
                base_form = row[0]
            else:
                # Fall back to canonical_label
                cur.execute(
                    "SELECT canonical_label FROM entities WHERE id = %s",
                    (entity_id,),
                )
                row = cur.fetchone()
                base_form = row[0] if row else "?"

            # Fetch entity properties
            cur.execute(
                "SELECT properties FROM entities WHERE id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            properties = row[0] if row and row[0] else None

            result = dispatch_surface_form(language, base_form, features or None, properties)

            cur.execute(
                "UPDATE mentions SET surface_form = %s, features = %s WHERE id = %s",
                (result, json.dumps(features) if features else None, mention_id),
            )
        self.state.db.commit()
        self.notify(f'Surface form set: "{result}"')

    # =====================
    # Import / Export
    # =====================

    def _busy_editing(self) -> bool:
        """True when an edit session is open; import/export must wait."""
        if self.state is None or self.state.view != "editor":
            return False
        self.notify("Save or cancel the edit first", severity="warning")
        return True

    def _prompt_export_path(self, title: str, default: str, do_export) -> None:
        """Ask for an export path; confirm before overwriting an existing file."""
        if self.state is None or self._busy_editing():
            return

        async def on_path(path: str | None) -> None:
            if not path or not path.strip():
                return
            path = path.strip()
            dest = Path(path).expanduser()
            if dest.exists():

                async def on_overwrite(confirmed: bool) -> None:
                    if confirmed:
                        do_export(path)

                self.push_screen(
                    ConfirmDialog("Overwrite file?", f"{dest} already exists."),
                    on_overwrite,
                )
                return
            do_export(path)

        self.push_screen(
            InputDialog(title, "File path:", default),
            on_path,
        )

    @safe_action
    def action_export_json(self) -> None:
        """Export the work as JSON to a file path."""
        self._prompt_export_path("Export JSON", "export.json", self._do_export_json)

    @safe_action
    def action_export_markdown(self) -> None:
        """Export the work as Markdown to a file path."""
        self._prompt_export_path("Export Markdown", "export.md", self._do_export_markdown)

    @safe_action
    def action_export_compile(self) -> None:
        """Export a chapter-joined manuscript Markdown file."""
        self._prompt_export_path(
            "Compile manuscript", "manuscript.md", self._do_export_compile
        )

    @safe_action
    def action_import_json(self) -> None:
        """Import a JSON export into the current work."""
        if self.state is None or self._busy_editing():
            return

        async def on_path(path: str | None) -> None:
            if not path or not path.strip():
                return
            path = path.strip()
            src = Path(path).expanduser()
            if not src.exists():
                self.notify(f"File not found: {src}", severity="error")
                return

            async def on_choice(choice: str) -> None:
                if choice not in ("confirm", "snapshot"):
                    return
                if choice == "snapshot" and not self._write_snapshot_now("before-import"):
                    return
                self._do_import_json(path)

            self.push_screen(
                SnapshotConfirmDialog(
                    "Import JSON?",
                    "This adds documents, entities, and related data to the current work.",
                ),
                on_choice,
            )

        self.push_screen(
            InputDialog("Import JSON", "File path:", ""),
            on_path,
        )

    @safe_action
    def action_snapshot(self) -> None:
        """Write a timestamped JSON snapshot of the whole work."""
        if self._busy_editing():
            return
        self._write_snapshot_now()

    def _write_snapshot_now(self, name: str | None = None) -> bool:
        """Write a snapshot now. Returns False (and notifies) if it failed.

        Synchronous on purpose: the callers that pass a name are about to
        destroy something and must not race the writer.
        """
        if self.state is None or self.state.db is None or self._littera_dir is None:
            self.notify("No work open — cannot snapshot", severity="error")
            return False
        try:
            dest = self._db(
                actions.write_work_snapshot,
                self.state.db,
                self._littera_dir.parent,
                name,
                label="Snapshot",
            )
        except OSError as exc:
            self.notify(f"Snapshot failed: {exc}", severity="error")
            return False
        if dest is DB_FAILED:
            return False
        self.notify(f"Snapshot written to {dest}")
        return True

    def _do_export_json(self, path: str) -> None:
        if self.state is None:
            return
        db = self.state.db
        self._run_io(
            "Exporting JSON…",
            lambda: actions.export_json_to_path(db, path),
            lambda dest: self.notify(f"Exported JSON to {dest}"),
            "Export failed",
        )

    def _do_export_markdown(self, path: str) -> None:
        if self.state is None:
            return
        db = self.state.db
        self._run_io(
            "Exporting Markdown…",
            lambda: actions.export_markdown_to_path(db, path),
            lambda dest: self.notify(f"Exported Markdown to {dest}"),
            "Export failed",
        )

    def _do_export_compile(self, path: str) -> None:
        if self.state is None:
            return
        db = self.state.db
        self._run_io(
            "Compiling manuscript…",
            lambda: actions.export_markdown_to_path(db, path, compile=True),
            lambda dest: self.notify(f"Compiled manuscript to {dest}"),
            "Compile failed",
        )

    def _do_import_json(self, path: str) -> None:
        if self.state is None:
            return
        db = self.state.db

        def done(counts: dict) -> None:
            if self.state is None:
                return
            parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
            summary = ", ".join(parts) if parts else "nothing"
            self.notify(f"Imported: {summary}")
            self.state.dispatch(ClearSelection())
            self._render_view()

        self._run_io(
            "Importing JSON…",
            lambda: actions.import_json_from_path(db, path),
            done,
            "Import failed",
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
        except LookupError as exc:
            self._db_failed("Read entity note", exc)
            return
        except psycopg.Error as exc:
            self._db_failed("Read entity note", exc)
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
        except LookupError as exc:
            self._db_failed("Read block", exc)
            return
        except psycopg.Error as exc:
            self._db_failed("Read block", exc)
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
            if self._db(
                actions.save_entity_note,
                self.state.db, session.target.id, work_id, new_text,
                label="Save note",
            ) is DB_FAILED:
                return

        elif session.target.kind == "block_text":
            if self._db(
                actions.save_block_text, self.state.db, session.target.id, new_text,
                label="Save block",
            ) is DB_FAILED:
                return

        else:
            return

        self.state.dispatch(ExitEditor())
        self._render_view()

    # =====================
    # Internal helpers
    # =====================

    def _start_edit(self, target: EditTarget, title: str, text: str) -> None:
        if self.state is None:
            return

        return_to = "entities" if target.kind == "entity_note" else "outline"
        self.state.dispatch(
            StartEdit(target=target, text=text, return_to=return_to, title=title)
        )
        self._render_view()

    def _editor_is_dirty(self) -> bool:
        """True when the editor holds text that differs from what was loaded."""
        if self.state is None:
            return False
        session = self.state.edit_session
        if session is None:
            return False
        return self._get_editor_text() != session.original_text

    def _confirm_discard(self, on_discard) -> None:
        """Run on_discard, asking first when the editor has unsaved text."""
        if not self._editor_is_dirty():
            on_discard()
            return

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                on_discard()

        self.push_screen(
            ConfirmDialog(
                "Discard unsaved changes?",
                "This edit has not been saved. Ctrl+S saves it.",
            ),
            on_confirm,
        )

    def _cancel_edit(self) -> None:
        if self.state is None:
            return
        if self.state.edit_session is None:
            return

        def discard() -> None:
            self.state.dispatch(ExitEditor())
            self._render_view()

        self._confirm_discard(discard)

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

    # =====================
    # Database calls
    # =====================

    def _db(self, func, *args, label: str | None = None, **kwargs):
        """Run one database call, surviving failure.

        psycopg leaves a connection in ``InFailedSqlTransaction`` after any
        error, so without a rollback the first failure is swallowed and the
        app dies several keystrokes later in unrelated code. Every TUI
        database call goes through here: roll back, tell the user, return
        :data:`DB_FAILED`.
        """
        what = label or getattr(func, "__name__", "operation").replace("_", " ")
        if self._io_busy:
            self.notify(
                "Busy with a long operation — try again in a moment.",
                severity="warning",
            )
            return DB_FAILED
        try:
            result = func(*args, **kwargs)
        except psycopg.Error as exc:
            self._db_failed(what, exc)
            return DB_FAILED
        except (LookupError, ReviewUpdateError, GuardViolation) as exc:
            # The row vanished, or a value the CLI layer validates was rejected
            # (e.g. a whitespace-only review description).
            self._db_failed(what, exc)
            return DB_FAILED
        else:
            # A pinned mentions/gaps pane describes the state before this
            # call. Keeping it would offer keys that act on rows that may
            # no longer exist.
            if self.state is not None and func.__module__.endswith("actions"):
                self.state.dispatch(ClearDetail())
            return result

    def _db_failed(self, what: str, exc: Exception) -> None:
        """Roll the connection back and surface the failure."""
        self._rollback()
        detail = str(exc).strip().splitlines()
        message = detail[0] if detail else type(exc).__name__
        logger.error("TUI database call failed (%s)", what, exc_info=exc)
        self.notify(f"{what} failed: {message}", severity="error")

    def _rollback(self) -> None:
        if self.state is None or self.state.db is None:
            return
        try:
            self.state.db.rollback()
        except psycopg.Error:
            logger.exception("rollback failed")

    def _run_io(self, busy_message, work, on_success, failure_prefix) -> None:
        """Run a slow database/file operation off the event loop.

        Import, export and gap detection all scan the whole work; doing that
        inline freezes the UI with no indication that anything is happening.
        """
        import asyncio

        if self._io_busy:
            self.notify("Another long operation is still running.", severity="warning")
            return

        self.notify(busy_message)
        # The worker shares this connection with the UI thread. Without this
        # flag a keypress could commit a half-finished import, breaking the
        # single-transaction promise in cli/io.py.
        self._io_busy = True

        async def runner() -> None:
            try:
                result = await asyncio.to_thread(work)
            except psycopg.Error as exc:
                self._db_failed(failure_prefix, exc)
                return
            except Exception as exc:
                # Structurally invalid JSON raises AttributeError/TypeError
                # mid-insert; without a rollback those pending rows would be
                # committed by the next successful action.
                self._rollback()
                logger.exception("%s failed", failure_prefix)
                self.notify(f"{failure_prefix}: {exc}", severity="error")
                return
            finally:
                self._io_busy = False
            on_success(result)

        self.run_worker(runner, group="io", exit_on_error=False)

    def _render_view(self) -> None:
        """Schedule a view re-render.

        Textual's `remove_children()` / `mount()` are async. If we call them
        synchronously, removals are deferred and we can briefly have duplicate ids
        in the DOM (crash on start / fast navigation).
        """

        if self.state is None:
            return

        # Pass the bound method, not a coroutine object: an exclusive worker
        # cancelled before it starts would otherwise leave an un-awaited
        # coroutine behind ("coroutine ... was never awaited").
        self.run_worker(
            self._render_view_async,
            group="render",
            exclusive=True,
            exit_on_error=False,
        )

    def _refresh_detail(self) -> None:
        """Re-read view data and update the detail pane *in place*.

        Highlighting a row must not rebuild the view: a fresh ListView starts
        at row 0, re-selects row 0 and re-renders, so the arrow keys could
        never leave the first item.
        """
        if self.state is None:
            return

        view = self.views.get(self.state.view)
        if view is None:
            return

        # The word count depends on the outline path, not on the highlighted
        # row, so it does not need recomputing here.
        try:
            self._refresh_data()
        except psycopg.Error as exc:
            self._db_failed("Refresh detail", exc)
            return

        # The footer is derived from check_action, which depends on the
        # selection: refresh it here too, not only when the view is rebuilt.
        self.refresh_bindings()

        try:
            detail = self.screen.query_one("#detail", Static)
        except NoMatches:
            return
        detail.update(view.detail_text(self.state))

    def _refresh_data(self) -> None:
        """Pre-load view data from DB into state before rendering."""
        if self.state is None:
            return
        if self.state.view == "outline":
            queries.refresh_outline(self.state)
        elif self.state.view == "entities":
            queries.refresh_entities(self.state)
        elif self.state.view == "alignments":
            queries.refresh_alignments(self.state)
        elif self.state.view == "reviews":
            queries.refresh_reviews(self.state)

    def _refresh_word_count(self) -> None:
        """Show saved-text word count for the current outline scope."""
        if self.state is None:
            return
        from littera.cli.words import count_scope, format_count

        document_id = None
        section_id = None
        scope = "work"
        for elem in self.state.path:
            if elem.kind == "document":
                document_id = elem.id
                scope = "document"
            elif elem.kind == "section":
                section_id = elem.id
                scope = "section"
        stats = count_scope(
            self.state.db, document_id=document_id, section_id=section_id
        )
        label = format_count(stats, scope)
        try:
            self.query_one("#word-count-bar", Static).update(label)
        except NoMatches:
            pass

    async def _render_view_async(self) -> None:
        if self.state is None:
            return

        try:
            self._refresh_data()
            self._refresh_word_count()
        except psycopg.Error as exc:
            # Render anyway, with the error where the user is looking, rather
            # than leaving the screen blank.
            self._db_failed("Refresh view", exc)
            self.state.dispatch(
                SetDetail(
                    "Database error\n\n"
                    f"{exc}\n\n"
                    "The connection was rolled back. Try the action again."
                )
            )

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
        elif self.state.view in ("outline", "entities", "alignments", "reviews"):
            try:
                nav = self.screen.query_one("#nav")
                nav.focus()
            except NoMatches:
                pass

        self.refresh_bindings()

    def _load_cfg(self) -> dict:
        work_dir = Path.cwd()
        littera_dir = work_dir / ".littera"
        if not littera_dir.exists():
            raise RuntimeError("Not a Littera work")
        return yaml.safe_load((littera_dir / "config.yml").read_text())

    # =====================
    # Event handlers
    # =====================

    def _parse_widget_id(self, raw: str) -> tuple[str | None, str]:
        # Textual ids can't start with a digit, so we prefix UUIDs.
        if "-" not in raw:
            return None, raw
        prefix, rest = raw.split("-", 1)
        if prefix in {"doc", "sec", "blk", "ent", "aln", "rev"}:
            return prefix, rest
        return None, raw

    def _set_selection_from_list_item(self, item_id: str) -> bool:
        """Set selection based on list item id.

        Returns True if selection changed.
        """

        if self.state is None:
            return False

        if self.state.view == "alignments":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            if prefix != "aln":
                # Not one of our rows (e.g. a pushed picker's "opt-N").
                return False
            alignment_id = raw_uuid

            current = self.state.alignments.selection
            if current.kind == "alignment" and current.id == alignment_id:
                return False

            self.state.dispatch(AlignmentsSelect(alignment_id))
            return True

        if self.state.view == "reviews":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            if prefix != "rev":
                return False
            review_id = raw_uuid

            current = self.state.reviews.selection
            if current.kind == "review" and current.id == review_id:
                return False

            self.state.dispatch(ReviewsSelect(review_id))
            return True

        if self.state.view == "entities":
            prefix, raw_uuid = self._parse_widget_id(item_id)
            if prefix != "ent":
                return False
            entity_id = raw_uuid

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

            if prefix not in prefix_kind_map:
                return False
            kind = prefix_kind_map[prefix]
            raw_id = raw_uuid

            current = self.state.outline.selection
            if current.kind == kind and current.id == raw_id:
                return False

            self.state.dispatch(OutlineSelect(kind=kind, item_id=raw_id))
            return True

        return False

    @staticmethod
    def _is_nav_list(event) -> bool:
        """True only for the main "#nav" list of the current view.

        Pushed dialogs (PickListDialog) own a ListView too and their messages
        bubble up to the App; their ids are not ours.
        """
        list_view = getattr(event, "list_view", None)
        return getattr(list_view, "id", None) == "nav"

    @safe_action
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update selection and right-hand detail on highlight."""
        if self.state is None:
            return
        if not self._is_nav_list(event):
            return

        item = event.item
        item_id = getattr(item, "id", None)
        if item_id is None:
            return

        changed = self._set_selection_from_list_item(str(item_id))
        if changed:
            # In place: rebuilding the view here would reset the highlight.
            self._refresh_detail()

    @safe_action
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Drill down on activation (Enter/click)."""
        if self.state is None:
            return
        if not self._is_nav_list(event):
            return

        item_id = getattr(event.item, "id", None)
        if item_id is None:
            return

        self._set_selection_from_list_item(str(item_id))

        # In Textual, Enter is often consumed by ListView to emit Selected.
        # Treat this as the user's "open" gesture in every list view, not just
        # the outline: the footer promises Enter everywhere.
        self.action_enter()

if __name__ == "__main__":
    LitteraApp().run()
