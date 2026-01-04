from dataclasses import dataclass, field
from typing import Optional, Literal, Any

from littera.tui.undo import UndoRedo


ViewName = Literal[
    "outline",
    "entities",
    "editor",
]

ModeName = Literal["browse", "edit", "command"]


@dataclass(frozen=True)
class PathElement:
    kind: str  # "work", "document", "section", "block"
    id: str
    title: str


EditKind = Literal["entity_note", "block_text"]


@dataclass(frozen=True)
class EditTarget:
    kind: EditKind
    id: str


@dataclass
class EditSession:
    target: EditTarget
    original_text: str
    current_text: str


@dataclass
class Selection:
    kind: Optional[str] = None  # "entity"
    id: Optional[str] = None


@dataclass
class AppState:
    view: ViewName = "outline"
    mode: ModeName = "browse"

    # Navigation path: work -> document -> section -> block
    # Empty path means at work level (showing documents)
    path: list[PathElement] = field(default_factory=list)

    # Entity selection (separate from outline navigation)
    entity_selection: Optional[Selection] = field(default_factory=Selection)

    # Editor overlay (None when not editing)
    edit_session: Optional[EditSession] = None

    # Undo/redo stack
    undo_redo: UndoRedo = field(default_factory=UndoRedo)

    # Context
    work: Optional[dict] = None
    db: Optional[Any] = None

    # Helpers
    @property
    def current_document(self) -> Optional[PathElement]:
        for p in reversed(self.path):
            if p.kind == "document":
                return p
        return None

    @property
    def current_section(self) -> Optional[PathElement]:
        for p in reversed(self.path):
            if p.kind == "section":
                return p
        return None

    @property
    def current_block(self) -> Optional[PathElement]:
        for p in reversed(self.path):
            if p.kind == "block":
                return p
        return None

    @property
    def can_go_back(self) -> bool:
        if self.view == "editor":
            return True
        if self.view == "entities":
            return self.entity_selection.kind == "entity"
        return len(self.path) > 0

    @property
    def nav_level(self) -> str:
        """Current navigation depth for views that need it."""
        if not self.path:
            return "documents"
        last = self.path[-1]
        if last.kind == "document":
            return "sections"
        elif last.kind == "section":
            return "blocks"
        return "documents"
