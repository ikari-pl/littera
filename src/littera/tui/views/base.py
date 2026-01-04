from abc import ABC, abstractmethod
from typing import Iterable
from textual.widget import Widget
from littera.tui.state import AppState


class View(ABC):
    name: str

    @abstractmethod
    def render(self, state: AppState) -> Iterable[Widget]: ...

    def handle_key(self, key: str, state: AppState) -> bool:
        return False

    def enter(self, state: AppState) -> None:
        pass

    def exit(self, state: AppState) -> None:
        pass
