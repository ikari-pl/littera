from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, ListView, Static

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
            parts.append(elem.title)
        return " > ".join(parts)

    def _get_hints(self, nav_level: str, has_selection: bool) -> str:
        """Get contextual hints for current navigation level."""
        base_hints = {
            "documents": "a:add doc  d:delete  Enter:drill  Esc:back  e:entities",
            "sections": "a:add sec  d:delete  Enter:drill  Esc:back  Ctrl+E:edit title",
            "blocks": "a:add blk  d:delete  Enter:edit  l:link entity  Esc:back",
        }
        return base_hints.get(nav_level, "a:add  d:delete  Enter:select  Esc:back")

    def _get_model_help(self, nav_level: str) -> str:
        """Get contextual help explaining the mental model."""
        h = self.HELP_STYLE
        e = self.HELP_END

        if nav_level == "documents":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document    ← you are here{e}
{h}       └─ Section{e}
{h}            └─ Block{e}

{h}Documents group sections together.{e}
{h}Each document is a standalone piece{e}
{h}— an article, essay, or chapter.{e}

{h}─────────────────────────{e}
{h}Enter  — drill into document{e}
{h}a      — add new document{e}
{h}e      — switch to Entities{e}
"""

        elif nav_level == "sections":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document{e}
{h}       └─ Section    ← you are here{e}
{h}            └─ Block{e}

{h}Sections divide a document.{e}
{h}Each section is a logical part{e}
{h}— a subchapter, scene, or argument.{e}

{h}─────────────────────────{e}
{h}Enter  — drill into section{e}
{h}Ctrl+E — edit title{e}
{h}Esc    — back to documents{e}
"""

        elif nav_level == "blocks":
            return f"""
{h}─── Littera Structure ───{e}

{h}Work{e}
{h}  └─ Document{e}
{h}       └─ Section{e}
{h}            └─ Block    ← you are here{e}

{h}Blocks are text fragments.{e}
{h}Each block has a language (en/pl/...){e}
{h}and can be linked to an Entity.{e}

{h}─────────────────────────{e}
{h}Enter  — edit block text{e}
{h}l      — link to Entity{e}
{h}Esc    — back to sections{e}
"""

        return ""

    def render(self, state: AppState):
        """Pure render from state.outline.items and state.outline.detail."""
        nav_level = state.nav_level
        model_help = self._get_model_help(nav_level)

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
                display = f"{label}  {outline_item.title}"
            items.append(ListItem(Static(display), id=f"{prefix}-{outline_item.id}"))

        # Detail: use pre-loaded detail, fall back to model help
        if state.outline.detail:
            detail = state.outline.detail
        elif not items:
            if not state.path:
                detail = f"No documents yet.\nPress 'a' to add one.\n{model_help}"
            else:
                last = state.path[-1]
                detail = f"No {nav_level} in '{last.title}' yet.\nPress 'a' to add one.\n{model_help}"
        else:
            detail = model_help

        breadcrumb = self._build_breadcrumb(state)
        hints = self._get_hints(state.nav_level, bool(state.entity_selection.id))

        return [
            Vertical(
                Static(breadcrumb, id="breadcrumb"),
                Horizontal(
                    ListView(*items, id="nav"),
                    Static(detail, id="detail"),
                    id="outline-layout",
                ),
                Static(hints, id="hint-bar"),
            )
        ]
