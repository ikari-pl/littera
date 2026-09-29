from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui import keymap
from littera.tui.state import AppState
from littera.tui.views.base import View

# Severity -> Rich markup color
_SEVERITY_COLOR = {
    "high": "red",
    "medium": "yellow",
    "low": "green",
}


class ReviewsView(View):
    name = "reviews"

    def detail_text(self, state: AppState) -> str:
        return state.reviews.detail or "Select a review"

    def selected_index(self, state: AppState) -> int:
        selected_id = state.reviews.selection.id
        if not selected_id:
            return 0
        for i, item in enumerate(state.reviews.items):
            if item.id == selected_id:
                return i
        return 0

    def render(self, state: AppState):
        """Pure render from state.reviews.items and state.reviews.detail."""
        hints = keymap.hint_bar(state)

        items = []
        for review_item in state.reviews.items:
            color = _SEVERITY_COLOR.get(review_item.severity, "yellow")
            scope_part = f" {review_item.scope}:" if review_item.scope else ""
            label = f"[{color}][{review_item.severity}][/{color}]{scope_part} {review_item.description}"
            items.append(
                ListItem(
                    Static(label),
                    id=f"rev-{review_item.id}",
                )
            )

        detail = self.detail_text(state)

        return [
            Vertical(
                Static("Reviews", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav", initial_index=self.selected_index(state)),
                    Static(detail, id="detail"),
                    id="reviews-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
