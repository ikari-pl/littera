from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

from littera.tui import keymap
from littera.tui.queries import display_title
from littera.tui.state import AppState
from littera.tui.views.base import View


class OutlineView(View):
    name = "outline"

    # Muted color for help text (Textual markup)
    HELP_STYLE = "[dim]"
    HELP_END = "[/dim]"

    def _build_breadcrumb(self, state: AppState) -> str:
        """Build breadcrumb path string like: Work > Doc > Section"""
        parts = ["Work"]
        for elem in state.path:
            parts.append(display_title(elem.title))
        return " > ".join(parts)

    def _get_model_help(self, nav_level: str) -> str:
        """Explain the mental model at this level.

        Keys are deliberately absent: the hint bar and `?` are generated from
        the bindings, and a second hand-written copy here drifted from them.
        """
        h = self.HELP_STYLE
        e = self.HELP_END

        here = {
            "documents": (
                "Document    ← you are here",
                (
                    "Documents group sections together.",
                    "Each document is a standalone piece",
                    "— an article, essay, or chapter.",
                ),
            ),
            "sections": (
                "Section    ← you are here",
                (
                    "Sections divide a document.",
                    "Each section is a logical part",
                    "— a subchapter, scene, or argument.",
                ),
            ),
            "blocks": (
                "Block    ← you are here",
                (
                    "Blocks are text fragments.",
                    "Each block has a language (en/pl/...)",
                    "and can be linked to an Entity.",
                ),
            ),
        }
        if nav_level not in here:
            return ""

        marked, prose = here[nav_level]
        levels = [
            ("Work", 0),
            ("Document", 1),
            ("Section", 2),
            ("Block", 3),
        ]
        lines = [f"{h}─── Littera Structure ───{e}", ""]
        for label, depth in levels:
            text = marked if marked.startswith(label) else label
            indent = "  " * depth + ("└─ " if depth else "")
            lines.append(f"{h}{indent}{text}{e}")
        lines.append("")
        lines.extend(f"{h}{line}{e}" for line in prose)
        return "\n" + "\n".join(lines) + "\n"

    def detail_text(self, state: AppState) -> str:
        """Detail pane text: pre-loaded detail, else the model help / empty state."""
        nav_level = state.nav_level
        model_help = self._get_model_help(nav_level)

        if state.outline.detail:
            return state.outline.detail
        if not state.outline.items:
            if not state.path:
                return f"No documents yet.\nPress 'a' to add one.\n{model_help}"
            last = state.path[-1]
            return (
                f"No {nav_level} in '{display_title(last.title)}' yet.\n"
                f"Press 'a' to add one.\n{model_help}"
            )
        return model_help

    def selected_index(self, state: AppState) -> int:
        selected_id = state.outline.selection.id
        if not selected_id:
            return 0
        for i, item in enumerate(state.outline.items):
            if item.id == selected_id:
                return i
        return 0

    def render(self, state: AppState):
        """Pure render from state.outline.items and state.outline.detail."""

        # Build list items from pre-loaded state
        items: list[ListItem] = []
        prefix_map = {"document": "doc", "section": "sec", "block": "blk"}
        label_map = {"document": "DOC", "section": "SEC", "block": "BLK"}

        for outline_item in state.outline.items:
            prefix = prefix_map[outline_item.kind]
            label = label_map[outline_item.kind]
            if outline_item.kind == "block":
                display = f"{label}  ({outline_item.language}) {outline_item.title}"
            else:
                display = f"{label}  {display_title(outline_item.title)}"
            items.append(ListItem(Static(display), id=f"{prefix}-{outline_item.id}"))

        detail = self.detail_text(state)

        breadcrumb = self._build_breadcrumb(state)
        hints = keymap.hint_bar(state)

        return [
            Vertical(
                Static(breadcrumb, id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav", initial_index=self.selected_index(state)),
                    Static(detail, id="detail"),
                    id="outline-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
