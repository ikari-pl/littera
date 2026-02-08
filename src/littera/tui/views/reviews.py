from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

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

    def render(self, state: AppState):
        """Pure render from state.reviews.items and state.reviews.detail."""
        hints = "a:add review  d:delete  o:outline  e:entities  Esc:back"

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

        detail = state.reviews.detail or "Select a review"

        return [
            Vertical(
                Static("Reviews", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav"),
                    Static(detail, id="detail"),
                    id="reviews-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
