from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static


class InputDialog(Screen[str]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, prompt: str, default: str = ""):
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._prompt),
            Input(value=self._default, id="input"),
            Button("OK", id="ok", variant="primary"),
            Button("Cancel", id="cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value or self._default)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            input_widget = self.query_one("#input", Input)
            self.dismiss(input_widget.value or self._default)
        else:
            self.dismiss(None)


class ConfirmDialog(Screen[bool]):
    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._message),
            Button("Yes", id="yes", variant="primary"),
            Button("No", id="no"),
            id="dialog",
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class RecoveryDialog(Screen[str]):
    """Dialog for WAL corruption recovery options.

    Returns "recover", "reinit", or "exit".
    """

    def __init__(self, message: str, can_recover: bool):
        super().__init__()
        self._message = message
        self._can_recover = can_recover

    def compose(self) -> ComposeResult:
        buttons = []
        if self._can_recover:
            buttons.append(
                Button("Recover (recommended)", id="recover", variant="primary")
            )
        buttons.append(
            Button("Re-initialize (lose all data)", id="reinit", variant="error")
        )
        buttons.append(Button("Exit", id="exit"))

        yield Vertical(
            Static("Database Recovery"),
            Static(self._message),
            *buttons,
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


class PickListDialog(Screen[str]):
    """Pick one option from a list. Returns the option id, or None on cancel."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]]):
        """options: list of (id, label)."""
        super().__init__()
        self._title = title
        self._options = options

    def compose(self) -> ComposeResult:
        from textual.widgets import ListItem, ListView

        items = [
            ListItem(Static(label), id=f"opt-{i}")
            for i, (_oid, label) in enumerate(self._options)
        ]
        body = (
            ListView(*items, id="pick-list")
            if items
            else Static("(no options)", id="pick-empty")
        )
        yield Vertical(
            Static(self._title),
            body,
            Button("Cancel", id="cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#pick-list").focus()
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event) -> None:
        idx = event.list_view.index
        if idx is None or idx < 0 or idx >= len(self._options):
            return
        self.dismiss(self._options[idx][0])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class HelpDialog(Screen[None]):
    """Model + shortcut cheatsheet for return-after-forgetting."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
        ("q", "close", "Close"),
    ]

    HELP_TEXT = """\
─── Littera Structure ───

Work
  └─ Document    (chapter, essay, article)
       └─ Section (scene, argument, part)
            └─ Block   (smallest text unit)

Entities are global concepts; Mentions bind them to blocks.
Alignments link two blocks (e.g. translation).
Reviews are scoped notes about quality or intent.

─── Keys ───
o  Outline     e  Entities     A  Alignments     R  Reviews
a  Add         d  Delete       Enter  Drill/Edit
Esc  Back      ?  This help    q  Quit
x/X  Export JSON/MD     C  Compile     i  Import
Ctrl+S save (in editor)   Ctrl+Up/Down reorder
"""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Help", id="help-title"),
            Static(self.HELP_TEXT, id="help-body"),
            Button("Close", id="close", variant="primary"),
            id="dialog",
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
