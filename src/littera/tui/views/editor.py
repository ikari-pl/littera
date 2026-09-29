from textual.containers import Vertical
from textual.widgets import Static

from littera.tui import keymap
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
            # The caller knew what it opened ("Block (en)", "Note: concept
            # Time"); rendering target.id showed the writer a raw UUID.
            title = session.title or "Editor"
            text = session.current_text

        try:
            from textual.widgets import TextArea

            editor = TextArea(text or "", id="editor")
        except ImportError:
            from textual.widgets import Input

            editor = Input(value=text or "", id="editor")

        # Undo/redo here is the text area's own, and only until Ctrl+S.
        hints = keymap.hint_bar(state)

        return [
            Vertical(
                Static(title, id="breadcrumb"),
                editor,
                Static(hints, id="hint-bar"),
                id="editor_layout",
            )
        ]
