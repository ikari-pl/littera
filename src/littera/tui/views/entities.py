from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui import keymap
from littera.tui.state import AppState
from littera.tui.views.base import View


class EntitiesView(View):
    name = "entities"

    def detail_text(self, state: AppState) -> str:
        return state.entities.detail or "Select an entity"

    def selected_index(self, state: AppState) -> int:
        selected_id = state.entities.selection.id
        if not selected_id:
            return 0
        for i, item in enumerate(state.entities.items):
            if item.id == selected_id:
                return i
        return 0

    def render(self, state: AppState):
        """Pure render from state.entities.items and state.entities.detail."""
        hints = keymap.hint_bar(state)

        items = []
        for entity_item in state.entities.items:
            items.append(
                ListItem(
                    Static(f"{entity_item.entity_type}: {entity_item.label}"),
                    id=f"ent-{entity_item.id}",
                )
            )

        detail = self.detail_text(state)

        return [
            Vertical(
                Static("Entities", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav", initial_index=self.selected_index(state)),
                    Static(detail, id="detail"),
                    id="entities-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
