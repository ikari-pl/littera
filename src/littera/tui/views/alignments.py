from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui.state import AppState
from littera.tui.views.base import View


class AlignmentsView(View):
    name = "alignments"

    def render(self, state: AppState):
        """Pure render from state.alignments.items and state.alignments.detail."""
        hints = "d:delete  g:gaps  o:outline  e:entities  Esc:back"

        items = []
        for alignment_item in state.alignments.items:
            display = (
                f"({alignment_item.source_lang}) {alignment_item.source_preview} "
                f"<-> ({alignment_item.target_lang}) {alignment_item.target_preview} "
                f"[{alignment_item.alignment_type}]"
            )
            items.append(
                ListItem(
                    Static(display),
                    id=f"aln-{alignment_item.id}",
                )
            )

        detail = state.alignments.detail or "Select an alignment"

        return [
            Vertical(
                Static("Alignments", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav"),
                    Static(detail, id="detail"),
                    id="alignments-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
