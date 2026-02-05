from textual.containers import Vertical
from textual.widgets import Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class EditorView(View):
    name = "editor"

    def render(self, state: AppState):
        session = state.edit_session
        if session is None:
            title = "Editor"
            text = ""
        else:
            target = session.target
            if target.kind == "entity_note":
                title = f"Note: {target.id}"
            elif target.kind == "block_text":
                title = f"Block: {target.id}"
            else:
                title = "Editor"
            text = session.current_text

        try:
            from textual.widgets import TextArea

            editor = TextArea(text or "", id="editor")
        except Exception:
            from textual.widgets import Input

            editor = Input(value=text or "", id="editor")

        hints = "Ctrl+S:save  Ctrl+Z:undo  Ctrl+Y:redo  Esc:cancel"

        return [
            Vertical(
                Static(title, id="breadcrumb"),
                editor,
                Static(hints, id="hint-bar"),
                id="editor_layout",
            )
        ]
