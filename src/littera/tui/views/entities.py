from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class EntitiesView(View):
    name = "entities"

    def render(self, state: AppState):
        """Pure render from state.entities.items and state.entities.detail."""
        hints = "a:add entity  n:edit note  o:outline  Esc:back"

        items = []
        for entity_item in state.entities.items:
            items.append(
                ListItem(
                    Static(f"{entity_item.entity_type}: {entity_item.label}"),
                    id=f"ent-{entity_item.id}",
                )
            )

        detail = state.entities.detail or "Select an entity"

        return [
            Vertical(
                Static("Entities", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav"),
                    Static(detail, id="detail"),
                    id="entities-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
