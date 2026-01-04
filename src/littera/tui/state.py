from dataclasses import dataclass, field
from typing import Optional, Literal, Any

from littera.tui.undo import UndoRedo

ViewName = Literal[
    "outline",
    "entities",
    "editor",
]

ModeName = Literal["browse", "edit", "command"]
NavLevel = Literal["documents", "sections", "blocks"]


@dataclass
class Selection:
    kind: Optional[str] = None
    id: Optional[str] = None


@dataclass
class AppState:
    view: ViewName = "outline"
    mode: ModeName = "browse"
    nav_level: NavLevel = "documents"
    document_id: Optional[str] = None
    section_id: Optional[str] = None
    selection: Selection = field(default_factory=Selection)
    work: Optional[dict] = None
    db: Optional[Any] = None

    editor_title: Optional[str] = None
    editor_text: str = ""
    editor_entity_id: Optional[str] = None
    editor_block_id: Optional[str] = None
    editor_block_lang: Optional[str] = None
    undo_redo: UndoRedo = field(default_factory=UndoRedo)
