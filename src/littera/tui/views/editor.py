from textual.containers import Vertical
from textual.widgets import Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class EditorView(View):
    name = "editor"

    def render(self, state: AppState):
        # Textual's TextArea is optional depending on version.
        try:
            from textual.widgets import TextArea

            editor = TextArea(state.editor_text or "", id="editor")
        except Exception:
            from textual.widgets import Input

            editor = Input(value=state.editor_text or "", id="editor")

        title = state.editor_title or "Editor"
        hint = "Ctrl+S: save   Esc: cancel"

        return [Vertical(Static(title), Static(hint), editor, id="editor_layout")]
