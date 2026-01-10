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
from typing import Optional, Literal, Any, Union


# =============================================================================
# Data Types
# =============================================================================

ModeName = Literal["browse", "edit", "command"]
ViewName = Literal["outline", "entities", "editor"]
EditKind = Literal["entity_note", "block_text"]


@dataclass(frozen=True)
class Selection:
    """Represents a selected item in a view."""
    kind: Optional[str] = None
    id: Optional[str] = None


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


# =============================================================================
# View States
# =============================================================================

@dataclass
class OutlineState:
    """State for outline navigation (documents -> sections -> blocks)."""
    path: list[PathElement] = field(default_factory=list)
    selection: Selection = field(default_factory=Selection)


@dataclass
class EntitiesState:
    """State for entities view."""
    selection: Selection = field(default_factory=Selection)


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
    pass


@dataclass(frozen=True)
class GotoEntities:
    """Switch to entities view."""
    pass


@dataclass(frozen=True)
class ClearSelection:
    """Clear selection in current view."""
    pass


@dataclass(frozen=True)
class OutlineSelect:
    """Select an item in outline view."""
    kind: str
    item_id: str


@dataclass(frozen=True)
class OutlineClearSelection:
    """Clear outline selection."""
    pass


@dataclass(frozen=True)
class OutlinePush:
    """Push a path element (drill down)."""
    element: PathElement


@dataclass(frozen=True)
class OutlinePop:
    """Pop the path (go back up)."""
    pass


@dataclass(frozen=True)
class EntitiesSelect:
    """Select an entity."""
    entity_id: str


@dataclass(frozen=True)
class EntitiesClearSelection:
    """Clear entity selection."""
    pass


@dataclass(frozen=True)
class StartEdit:
    """Start editing (opens editor overlay)."""
    target: EditTarget
    text: str
    return_to: ViewName


@dataclass(frozen=True)
class ExitEditor:
    """Exit editor overlay."""
    pass


# Action union type for type checking
Action = Union[
    GotoOutline,
    GotoEntities,
    ClearSelection,
    OutlineSelect,
    OutlineClearSelection,
    OutlinePush,
    OutlinePop,
    EntitiesSelect,
    EntitiesClearSelection,
    StartEdit,
    ExitEditor,
]


# =============================================================================
# Reducer
# =============================================================================

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

        case GotoEntities():
            state.view = "entities"
            state.active_base = "entities"

        case ClearSelection():
            if state.view == "outline":
                state.outline.selection = Selection()
            elif state.view == "entities":
                state.entities.selection = Selection()

        case OutlineSelect(kind=kind, item_id=item_id):
            state.outline.selection = Selection(kind=kind, id=item_id)

        case OutlineClearSelection():
            state.outline.selection = Selection()

        case OutlinePush(element=element):
            state.outline.path.append(element)
            state.outline.selection = Selection()

        case OutlinePop():
            if state.outline.path:
                state.outline.path.pop()
                state.outline.selection = Selection()

        case EntitiesSelect(entity_id=entity_id):
            state.entities.selection = Selection(kind="entity", id=entity_id)

        case EntitiesClearSelection():
            state.entities.selection = Selection()

        case StartEdit(target=target, text=text, return_to=return_to):
            session = EditSession(
                target=target,
                original_text=text,
                current_text=text,
                return_to=return_to,
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

# Import here to avoid circular import issues
from littera.tui.undo import UndoRedo


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
    editor: Optional[EditorOverlay] = None

    # Undo/redo state (scoped to edit sessions)
    undo_redo: UndoRedo = field(default_factory=UndoRedo)

    # Work context (loaded from config.yml)
    work: Optional[dict[str, Any]] = None

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
    def edit_session(self) -> Optional[EditSession]:
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
    def current_document(self) -> Optional[PathElement]:
        """The current document in the path, if any."""
        for elem in self.outline.path:
            if elem.kind == "document":
                return elem
        return None

    @property
    def current_section(self) -> Optional[PathElement]:
        """The current section in the path, if any."""
        for elem in self.outline.path:
            if elem.kind == "section":
                return elem
        return None

    @property
    def path(self) -> list[PathElement]:
        """Shorthand for outline.path - the current navigation path."""
        return self.outline.path
