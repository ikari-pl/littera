import logging
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

logger = logging.getLogger(__name__)


class InputDialog(ModalScreen[str]):
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "cancel", "Cancel")]

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


class ConfirmDialog(ModalScreen[bool]):
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
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
            Static("y: yes   n/Esc: no"),
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


class SnapshotConfirmDialog(ModalScreen[str]):
    """Confirm a destructive action, with the option to snapshot first.

    Returns "cancel", "confirm", or "snapshot" (write a snapshot, then go
    ahead). Focus starts on No: a reflexive Enter must not delete anything.
    """

    AUTO_FOCUS = "#no"

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("y", "confirm", "Yes"),
        ("s", "snapshot", "Snapshot first"),
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
            Static("y: yes   s: snapshot first, then yes   n/Esc: cancel"),
            Button("No", id="no"),
            Button("Snapshot first, then continue", id="snapshot"),
            Button("Yes", id="yes", variant="error"),
            id="dialog",
        )

    def action_confirm(self) -> None:
        self.dismiss("confirm")

    def action_snapshot(self) -> None:
        self.dismiss("snapshot")

    def action_cancel(self) -> None:
        self.dismiss("cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {"yes": "confirm", "snapshot": "snapshot"}
        self.dismiss(mapping.get(event.button.id or "", "cancel"))


class RecoveryDialog(ModalScreen[str]):
    """Dialog for WAL corruption recovery options.

    Returns "recover", "reinit", or "exit".

    Focus starts on Exit, never on "Re-initialize": the default AUTO_FOCUS of
    "*" grabs the first focusable widget, so a reflexive Enter used to wipe
    the database.
    """

    AUTO_FOCUS = "#exit"

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "leave", "Exit")]

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
        # Exit comes before the destructive option, in reading order as well
        # as in focus order.
        buttons.append(Button("Exit", id="exit"))
        buttons.append(
            Button("Re-initialize (lose all data)", id="reinit", variant="error")
        )

        yield Vertical(
            Static("Database Recovery"),
            VerticalScroll(Static(self._message), id="recovery-log"),
            *buttons,
            id="dialog",
        )

    def action_leave(self) -> None:
        self.dismiss("exit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


class PickListDialog(ModalScreen[str]):
    """Pick one option from a list. Returns the option id, or None on cancel."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "cancel", "Cancel")]

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
        except NoMatches:
            # An empty picker has no list to focus; the Cancel button keeps focus.
            logger.debug("pick list not present at mount; leaving focus alone")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_highlighted(self, event) -> None:
        # The picker is a pushed Screen, so its ListView messages would bubble
        # to the App and be mistaken for a selection in the base view.
        event.stop()

    def on_list_view_selected(self, event) -> None:
        event.stop()
        idx = event.list_view.index
        if idx is None or idx < 0 or idx >= len(self._options):
            return
        self.dismiss(self._options[idx][0])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class HelpDialog(ModalScreen[None]):
    """Model + shortcut cheatsheet for return-after-forgetting.

    The text is generated from the app's bindings (see `littera.tui.keymap`)
    and passed in, so it cannot drift from the keys that actually work.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def __init__(self, help_text: str):
        super().__init__()
        self._help_text = help_text

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Help", id="help-title"),
            VerticalScroll(Static(self._help_text, id="help-body"), id="help-scroll"),
            Button("Close", id="close", variant="primary"),
            id="dialog",
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
