from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui import keymap
from littera.tui.state import AppState
from littera.tui.views.base import View


class AlignmentsView(View):
    name = "alignments"

    def detail_text(self, state: AppState) -> str:
        return state.alignments.detail or "Select an alignment"

    def selected_index(self, state: AppState) -> int:
        selected_id = state.alignments.selection.id
        if not selected_id:
            return 0
        for i, item in enumerate(state.alignments.items):
            if item.id == selected_id:
                return i
        return 0

    def render(self, state: AppState):
        """Pure render from state.alignments.items and state.alignments.detail."""
        hints = keymap.hint_bar(state)

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

        detail = self.detail_text(state)

        return [
            Vertical(
                Static("Alignments", id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav", initial_index=self.selected_index(state)),
                    Static(detail, id="detail"),
                    id="alignments-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
