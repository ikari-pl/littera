from abc import ABC, abstractmethod
from collections.abc import Iterable

from textual.widget import Widget

from littera.tui.state import AppState


class View(ABC):
    name: str

    @abstractmethod
    def render(self, state: AppState) -> Iterable[Widget]: ...

    def detail_text(self, state: AppState) -> str:
        """Text for the `#detail` pane.

        Kept separate from render() so the app can refresh the detail pane in
        place instead of tearing down and re-mounting the whole view.
        """
        return ""

    def selected_index(self, state: AppState) -> int:
        """Index of the selected row in the `#nav` list, 0 if none matches.

        Used as ListView's initial_index so a rebuild does not snap the
        highlight (and therefore the selection) back to the first row.
        """
        return 0

    def handle_key(self, key: str, state: AppState) -> bool:
        return False

    def enter(self, state: AppState) -> None:
        pass

    def exit(self, state: AppState) -> None:
        pass
