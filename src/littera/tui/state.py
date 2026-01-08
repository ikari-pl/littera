from dataclasses import dataclass, field
from typing import Optional, Literal, Any, Union
from pathlib import Path

from littera.tui.undo import UndoRedo


# Data types and enums

ModeName = Literal["browse", "edit", "command"]

ViewName = Literal["outline", "entities", "editor"]

EditKind = Literal["entity_note", "block_text"]


# Selection
@dataclass(frozen=True)
class Selection:
    kind: Optional[str] = None
    id: Optional[str] = None


# Path elements for outline navigation
@dataclass(frozen=True)
class PathElement:
    kind: str  # "work", "document", "section", "block"
    id: str
    title: str


# Edit session
@dataclass
class EditSession:
    target: "EditTarget"
    original_text: str
    current_text: str
    return_to: Literal["outline", "entities"]


# Edit target
@dataclass(frozen=True)
class EditTarget:
    kind: EditKind
    id: str


# View states
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


# App state
@dataclass
class AppState:
    """App state with explicit view contexts."""

    # Current mode/view
    view: ViewName = "browse"

    # Context for each view
    active_base: ViewName = "browse"  # The current underlying view
    outline: OutlineState = field(default_factory=OutlineState)
    entities: EntitiesState = field(default_factory=EntitiesState)
    editor: Optional[EditorOverlay] = None

    # Undo/redo state
    undo_redo: UndoRedo = field(default_factory=UndoRedo)

    # Work context
    work: Optional[dict[str, Any]] = None

    # Database connection
    db: Any = None


# Actions


@dataclass(frozen=True)
class GotoOutline:
    pass


@dataclass(frozen=True)
class GotoEntities:
    pass


@dataclass(frozen=True)
class ClearSelection:
    pass


@dataclass(frozen=True)
class OutlineSelect:
    kind: str
    item_id: str


@dataclass(frozen=True)
class OutlineClearSelection:
    pass


@dataclass(frozen=True)
class OutlinePush:
    element: PathElement


@dataclass(frozen=True)
class OutlinePop:
    pass


@dataclass(frozen=True)
class EntitiesSelect:
    entity_id: str


@dataclass(frozen=True)
class EntitiesClearSelection:
    pass


@dataclass(frozen=True)
class StartEdit:
    target: EditTarget
    text: str
    return_to: ViewName


@dataclass(frozen=True)
class ExitEditor:
    pass


# Action type
Action = (
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
)
