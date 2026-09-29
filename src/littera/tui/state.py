"""
TUI state management and actions for Phase 1B.

This module provides the core state management and action definitions
for the Textual User Interface.

Architecture:
- Actions are frozen dataclasses representing state transitions
- reduce(state, action) is a pure function that returns updated state
- AppState.dispatch(action) mutates self by applying reduce
- Computed properties provide convenient access to derived state
"""

from dataclasses import dataclass, field
from typing import Any, Literal

# =============================================================================
# Data Types
# =============================================================================

ModeName = Literal["browse", "edit", "command"]
ViewName = Literal["outline", "entities", "editor", "alignments", "reviews"]
EditKind = Literal["entity_note", "block_text"]


@dataclass(frozen=True)
class Selection:
    """Represents a selected item in a view."""
    kind: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class PathElement:
    """A single element in the outline navigation path."""
    kind: str  # "work", "document", "section", "block"
    id: str
    title: str


@dataclass(frozen=True)
class EditTarget:
    """Identifies what is being edited."""
    kind: EditKind
    id: str


@dataclass
class EditSession:
    """Active editing session state."""
    target: EditTarget
    original_text: str
    current_text: str
    return_to: ViewName
    # Human title of what is being edited ("Block (en)", "Note: concept Time").
    # The caller always knows it; without storing it the editor could only
    # show the row's UUID.
    title: str = "Editor"


# =============================================================================
# View Data (populated by queries.py, consumed by views)
# =============================================================================

@dataclass(frozen=True)
class OutlineItem:
    """A single item in the outline list (document, section, or block)."""
    id: str
    kind: str  # "document", "section", "block"
    title: str
    language: str = ""  # Only for blocks


@dataclass(frozen=True)
class EntityItem:
    """A single entity in the entities list."""
    id: str
    entity_type: str
    label: str


@dataclass(frozen=True)
class AlignmentItem:
    """A single alignment in the alignments list."""
    id: str
    source_lang: str
    source_preview: str
    target_lang: str
    target_preview: str
    alignment_type: str


@dataclass(frozen=True)
class ReviewItem:
    """A single review in the reviews list."""
    id: str
    severity: str       # "low", "medium", "high"
    scope: str          # "work", "document", "section", "block", "entity", "alignment" or ""
    issue_type: str     # or ""
    description: str    # truncated preview


# =============================================================================
# View States
# =============================================================================

@dataclass
class OutlineState:
    """State for outline navigation (documents -> sections -> blocks)."""
    path: list[PathElement] = field(default_factory=list)
    selection: Selection = field(default_factory=Selection)
    items: list[OutlineItem] = field(default_factory=list)
    detail: str = ""
    # Explicit, reducer-owned override of the detail pane (e.g. "show mentions").
    # None means "derive detail from the current selection".
    detail_override: str | None = None


@dataclass
class EntitiesState:
    """State for entities view."""
    selection: Selection = field(default_factory=Selection)
    items: list[EntityItem] = field(default_factory=list)
    detail: str = ""
    detail_override: str | None = None


@dataclass
class AlignmentsState:
    """State for alignments view."""
    selection: Selection = field(default_factory=Selection)
    items: list[AlignmentItem] = field(default_factory=list)
    detail: str = ""
    detail_override: str | None = None


@dataclass
class ReviewsState:
    """State for reviews view."""
    items: list[ReviewItem] = field(default_factory=list)
    selection: Selection = field(default_factory=Selection)
    detail: str = ""
    detail_override: str | None = None


@dataclass
class EditorOverlay:
    """Overlay state for editing (push/pop on top of a base view)."""
    session: EditSession
    return_to: ViewName


# =============================================================================
# Actions
# =============================================================================

@dataclass(frozen=True)
class GotoOutline:
    """Switch to outline view."""


@dataclass(frozen=True)
class GotoEntities:
    """Switch to entities view."""


@dataclass(frozen=True)
class GotoAlignments:
    """Switch to alignments view."""


@dataclass(frozen=True)
class AlignmentsSelect:
    """Select an alignment."""
    alignment_id: str


@dataclass(frozen=True)
class AlignmentsClearSelection:
    """Clear alignment selection."""


@dataclass(frozen=True)
class ClearSelection:
    """Clear selection in current view."""


@dataclass(frozen=True)
class OutlineSelect:
    """Select an item in outline view."""
    kind: str
    item_id: str


@dataclass(frozen=True)
class OutlineClearSelection:
    """Clear outline selection."""


@dataclass(frozen=True)
class OutlinePush:
    """Push a path element (drill down)."""
    element: PathElement


@dataclass(frozen=True)
class OutlinePop:
    """Pop the path (go back up)."""


@dataclass(frozen=True)
class EntitiesSelect:
    """Select an entity."""
    entity_id: str


@dataclass(frozen=True)
class EntitiesClearSelection:
    """Clear entity selection."""


@dataclass(frozen=True)
class GotoReviews:
    """Switch to reviews view."""


@dataclass(frozen=True)
class ReviewsSelect:
    """Select a review."""
    review_id: str


@dataclass(frozen=True)
class ReviewsClearSelection:
    """Clear review selection."""


@dataclass(frozen=True)
class StartEdit:
    """Start editing (opens editor overlay)."""
    target: EditTarget
    text: str
    return_to: ViewName
    title: str = "Editor"


@dataclass(frozen=True)
class ExitEditor:
    """Exit editor overlay."""


@dataclass(frozen=True)
class ClearDetail:
    """Drop any pinned detail text; panes return to live data."""


@dataclass(frozen=True)
class SetDetail:
    """Pin an explicit detail pane text for the current view.

    The override survives data refreshes (so "show mentions" / "show gaps"
    stay on screen) and is cleared by the reducer on any selection change.
    """
    text: str


# Action union type for type checking
Action = (
    GotoOutline
    | GotoEntities
    | GotoAlignments
    | GotoReviews
    | ClearSelection
    | OutlineSelect
    | OutlineClearSelection
    | OutlinePush
    | OutlinePop
    | EntitiesSelect
    | EntitiesClearSelection
    | AlignmentsSelect
    | AlignmentsClearSelection
    | ReviewsSelect
    | ReviewsClearSelection
    | StartEdit
    | ExitEditor
    | ClearDetail
    | SetDetail
)


def _view_state(state: "AppState", view: str):
    """The per-view state object for a view name, or None."""
    if view == "outline":
        return state.outline
    if view == "entities":
        return state.entities
    if view == "alignments":
        return state.alignments
    if view == "reviews":
        return state.reviews
    return None


# =============================================================================
# Reducer
# =============================================================================

def _clear_all_overrides(state) -> None:
    """Clear every view's pinned detail text."""
    for view_state in (state.outline, state.entities, state.alignments, state.reviews):
        view_state.detail_override = None


def reduce(state: "AppState", action: Action) -> None:
    """
    Apply an action to mutate state.

    This is the central state transition logic. All state changes flow through here.
    The function mutates state in place (Textual works better with mutable state).
    """
    match action:
        case GotoOutline():
            state.view = "outline"
            state.active_base = "outline"
            # A pinned mentions/gaps pane belongs to the moment it was asked
            # for, not to every later visit.
            _clear_all_overrides(state)

        case GotoEntities():
            state.view = "entities"
            state.active_base = "entities"
            # A pinned mentions/gaps pane belongs to the moment it was asked
            # for, not to every later visit.
            _clear_all_overrides(state)

        case GotoAlignments():
            state.view = "alignments"
            state.active_base = "alignments"
            # A pinned mentions/gaps pane belongs to the moment it was asked
            # for, not to every later visit.
            _clear_all_overrides(state)

        case GotoReviews():
            state.view = "reviews"
            state.active_base = "reviews"
            # A pinned mentions/gaps pane belongs to the moment it was asked
            # for, not to every later visit.
            _clear_all_overrides(state)

        case ClearSelection():
            view_state = _view_state(state, state.view)
            if view_state is not None:
                view_state.selection = Selection()
                view_state.detail_override = None

        case OutlineSelect(kind=kind, item_id=item_id):
            state.outline.selection = Selection(kind=kind, id=item_id)
            state.outline.detail_override = None

        case OutlineClearSelection():
            state.outline.selection = Selection()
            state.outline.detail_override = None

        case OutlinePush(element=element):
            state.outline.path.append(element)
            state.outline.selection = Selection()
            state.outline.detail_override = None

        case OutlinePop():
            if state.outline.path:
                state.outline.path.pop()
                state.outline.selection = Selection()
                state.outline.detail_override = None

        case EntitiesSelect(entity_id=entity_id):
            state.entities.selection = Selection(kind="entity", id=entity_id)
            state.entities.detail_override = None

        case EntitiesClearSelection():
            state.entities.selection = Selection()
            state.entities.detail_override = None

        case AlignmentsSelect(alignment_id=alignment_id):
            state.alignments.selection = Selection(kind="alignment", id=alignment_id)
            state.alignments.detail_override = None

        case AlignmentsClearSelection():
            state.alignments.selection = Selection()
            state.alignments.detail_override = None

        case ReviewsSelect(review_id=review_id):
            state.reviews.selection = Selection(kind="review", id=review_id)
            state.reviews.detail_override = None

        case ReviewsClearSelection():
            state.reviews.selection = Selection()
            state.reviews.detail_override = None

        case ClearDetail():
            _clear_all_overrides(state)

        case SetDetail(text=text):
            view_state = _view_state(state, state.view)
            if view_state is not None:
                view_state.detail_override = text

        case StartEdit(target=target, text=text, return_to=return_to, title=title):
            session = EditSession(
                target=target,
                original_text=text,
                current_text=text,
                return_to=return_to,
                title=title,
            )
            state.editor = EditorOverlay(session=session, return_to=return_to)
            state.view = "editor"

        case ExitEditor():
            if state.editor is not None:
                return_to = state.editor.return_to
                state.editor = None
                state.view = return_to


# =============================================================================
# App State
# =============================================================================

@dataclass
class AppState:
    """
    Central application state with explicit view contexts.

    This is a mutable dataclass. State changes happen via dispatch(action),
    which calls the reduce function to apply transitions.
    """

    # Current view
    view: ViewName = "outline"

    # The base view (outline or entities) - editor is an overlay
    active_base: ViewName = "outline"

    # View-specific state
    outline: OutlineState = field(default_factory=OutlineState)
    entities: EntitiesState = field(default_factory=EntitiesState)
    alignments: AlignmentsState = field(default_factory=AlignmentsState)
    reviews: ReviewsState = field(default_factory=ReviewsState)
    editor: EditorOverlay | None = None

    # Work context (loaded from config.yml)
    work: dict[str, Any] | None = None

    # Database connection (managed by app lifecycle)
    db: Any = None

    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------

    def dispatch(self, action: Action) -> None:
        """Apply an action to update state."""
        reduce(self, action)

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def edit_session(self) -> EditSession | None:
        """Current edit session, if editor is open."""
        if self.editor is not None:
            return self.editor.session
        return None

    @property
    def entity_selection(self) -> Selection:
        """
        Current selection based on active view.

        In outline view: returns outline selection
        In entities view: returns entity selection
        In editor: returns selection from the view we came from
        """
        if self.view == "entities":
            return self.entities.selection
        elif self.view == "editor" and self.editor is not None:
            if self.editor.return_to == "entities":
                return self.entities.selection
            return self.outline.selection
        return self.outline.selection

    @property
    def nav_level(self) -> str:
        """
        Current navigation level in outline view.

        Returns: "documents", "sections", or "blocks"
        """
        path = self.outline.path
        if not path:
            return "documents"
        last = path[-1]
        if last.kind == "document":
            return "sections"
        elif last.kind == "section":
            return "blocks"
        return "documents"

    @property
    def current_document(self) -> PathElement | None:
        """The current document in the path, if any."""
        for elem in self.outline.path:
            if elem.kind == "document":
                return elem
        return None

    @property
    def current_section(self) -> PathElement | None:
        """The current section in the path, if any."""
        for elem in self.outline.path:
            if elem.kind == "section":
                return elem
        return None

    @property
    def path(self) -> list[PathElement]:
        """Shorthand for outline.path - the current navigation path."""
        return self.outline.path
