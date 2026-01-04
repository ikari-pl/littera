from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static


class InputDialog(Screen[str]):
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            input_widget = self.query_one("#input", Input)
            self.dismiss(input_widget.value or self._default)
        else:
            self.dismiss(None)


class ConfirmDialog(Screen[bool]):
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
