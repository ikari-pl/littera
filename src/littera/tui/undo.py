"""Lightweight undo/redo buffer.

This stores edits at the TUI level, not the database layer.

- Each edit holds: target, kind, old, new
- Redo stack only grows while performing undo
- Stacks are cleared when a view exits or mode changes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Literal, Optional, List


EditKind = Literal[
    "entity_note",
    "block_text",
]

EditTarget = NamedTuple("EditTarget", [("kind", EditKind), ("id", str)])


@dataclass(frozen=True)
class Edit:
    target: EditTarget
    old: str
    new: str


class UndoRedo:
    """Minimal undo/redo stack for TUI edits."""

    def __init__(self) -> None:
        self._undo: List[Edit] = []
        self._redo: List[Edit] = []

    def record(self, target: EditTarget, old: str, new: str) -> None:
        """Record an edit and clear redo history."""
        self._undo.append(Edit(target=target, old=old, new=new))
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def pop_undo(self) -> Optional[Edit]:
        """Pop last edit for undo; move it to redo."""
        if not self._undo:
            return None
        edit = self._undo.pop()
        self._redo.append(edit)
        return edit

    def pop_redo(self) -> Optional[Edit]:
        """Pop last undone edit for redo; move it back to undo."""
        if not self._redo:
            return None
        edit = self._redo.pop()
        self._undo.append(edit)
        return edit

    def clear(self) -> None:
        """Clear all history (called on mode/view change)."""
        self._undo.clear()
        self._redo.clear()

    def __len__(self) -> int:
        """Number of undoable edits."""
        return len(self._undo)

    def redo_len(self) -> int:
        """Number of redoable edits."""
        return len(self._redo)
