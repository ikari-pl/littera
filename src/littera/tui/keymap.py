"""The TUI's key vocabulary, and where each key is valid.

One list of bindings, one table of availability rules, and three renderers
built from them: the footer (via ``App.check_action``), the per-view hint bar,
and the help overlay. Hand-written copies of the same information drifted from
reality — a key that worked was not advertised, and keys that did nothing were.

Availability is a pure function of :class:`~littera.tui.state.AppState`, so it
is testable without running the app.
"""

from __future__ import annotations

from collections.abc import Callable

# =============================================================================
# Bindings — the single source of truth (LitteraApp.BINDINGS is this list)
# =============================================================================

BINDINGS: list[tuple[str, str, str]] = [
    ("q", "quit", "Quit"),
    ("escape", "back", "Back"),
    ("o", "outline", "Outline"),
    ("e", "entities", "Entities"),
    ("A", "alignments", "Alignments"),
    ("R", "reviews", "Reviews"),
    ("enter", "enter", "Open"),
    ("a", "add_item", "Add"),
    ("d", "delete_item", "Delete"),
    ("ctrl+e", "edit_title", "Edit Title"),
    ("N", "edit_note", "Edit Note"),
    ("l", "link_entity", "Link Entity"),
    ("ctrl+l", "set_language", "Set Language"),
    ("M", "show_mentions", "Show Mentions"),
    ("S", "set_surface", "Set Surface"),
    ("D", "delete_mention", "Delete Mention"),
    ("L", "entity_labels", "Labels"),
    ("p", "entity_properties", "Properties"),
    ("g", "show_gaps", "Find Gaps"),
    ("ctrl+up", "move_up", "Move Up"),
    ("ctrl+down", "move_down", "Move Down"),
    ("ctrl+s", "save", "Save"),
    ("x", "export_json", "Export JSON"),
    ("X", "export_markdown", "Export MD"),
    ("C", "export_compile", "Compile MD"),
    ("i", "import_json", "Import JSON"),
    ("s", "snapshot", "Snapshot"),
    ("question_mark", "show_help", "Help"),
]


# Keys that mean the same thing everywhere. They stay out of the per-view hint
# bar (which has one line) and are listed in the help overlay instead.
GLOBAL_ACTIONS = frozenset(
    {
        "quit",
        "show_help",
        "outline",
        "entities",
        "alignments",
        "reviews",
        "export_json",
        "export_markdown",
        "export_compile",
        "import_json",
        "snapshot",
    }
)


# =============================================================================
# Availability
# =============================================================================

def _sel(state, view: str):
    """The selection of one view, or an empty one."""
    from littera.tui.state import Selection

    holder = {
        "outline": getattr(state, "outline", None),
        "entities": getattr(state, "entities", None),
        "alignments": getattr(state, "alignments", None),
        "reviews": getattr(state, "reviews", None),
    }.get(view)
    if holder is None:
        return Selection()
    return holder.selection


def _outline_kind(state) -> str | None:
    sel = _sel(state, "outline")
    return sel.kind if sel.id else None


def _has_selection(state) -> bool:
    """True when the current view has something selected to act on."""
    view = state.view
    if view not in ("outline", "entities", "alignments", "reviews"):
        return False
    return bool(_sel(state, view).id)


def _is_block(state) -> bool:
    return state.view == "outline" and _outline_kind(state) == "block"


def _not_editing(state) -> bool:
    return state.view != "editor"


AVAILABILITY: dict[str, Callable[[object], bool]] = {
    "quit": lambda s: True,
    "show_help": lambda s: True,
    "back": lambda s: True,
    "outline": lambda s: s.view != "outline",
    "entities": lambda s: s.view != "entities",
    "alignments": lambda s: s.view != "alignments",
    "reviews": lambda s: s.view != "reviews",
    "save": lambda s: s.view == "editor",
    "enter": lambda s: (
        (s.view == "outline" and _outline_kind(s) is not None)
        or (s.view == "entities" and bool(_sel(s, "entities").id))
        or (s.view == "reviews" and bool(_sel(s, "reviews").id))
    ),
    "add_item": lambda s: s.view in ("outline", "entities", "alignments", "reviews"),
    "delete_item": _has_selection,
    "edit_title": lambda s: (
        (s.view == "outline" and _outline_kind(s) in ("document", "section"))
        or (s.view == "reviews" and bool(_sel(s, "reviews").id))
    ),
    "edit_note": lambda s: s.view == "entities" and bool(_sel(s, "entities").id),
    "link_entity": _is_block,
    "set_language": _is_block,
    "show_mentions": _is_block,
    "set_surface": _is_block,
    "delete_mention": _is_block,
    "entity_labels": lambda s: s.view == "entities" and bool(_sel(s, "entities").id),
    "entity_properties": lambda s: s.view == "entities"
    and bool(_sel(s, "entities").id),
    "show_gaps": lambda s: s.view == "alignments",
    "move_up": lambda s: s.view == "outline"
    and _outline_kind(s) in ("document", "section", "block"),
    "move_down": lambda s: s.view == "outline"
    and _outline_kind(s) in ("document", "section", "block"),
    "export_json": _not_editing,
    "export_markdown": _not_editing,
    "export_compile": _not_editing,
    "import_json": _not_editing,
    "snapshot": _not_editing,
}


def is_available(state, action: str) -> bool:
    """True when ``action`` can do something in the current state.

    Unknown actions are allowed: Textual binds its own (command palette,
    focus movement) and this table must not disable them.
    """
    rule = AVAILABILITY.get(action)
    if rule is None:
        return True
    if state is None:
        # Before the work is open, only the keys that need no work at all.
        return action in ("quit", "show_help")
    return bool(rule(state))


# =============================================================================
# Rendering
# =============================================================================

_KEY_DISPLAY = {
    "escape": "Esc",
    "enter": "Enter",
    "question_mark": "?",
    "ctrl+e": "Ctrl+E",
    "ctrl+l": "Ctrl+L",
    "ctrl+s": "Ctrl+S",
    "ctrl+up": "Ctrl+Up",
    "ctrl+down": "Ctrl+Down",
}


def key_display(key: str) -> str:
    """How a binding key is written for a human."""
    return _KEY_DISPLAY.get(key, key)


def available_bindings(state) -> list[tuple[str, str, str]]:
    """The (key, action, description) triples valid right now."""
    return [b for b in BINDINGS if is_available(state, b[1])]


# The text area binds these itself; they are not app bindings and only live
# as long as the edit session.
EDITOR_LOCAL_HINT = "Ctrl+Z/Ctrl+Y:undo/redo (until you save)"


def hint_bar(state) -> str:
    """One line of the keys that do something here, global keys aside."""
    parts = [
        f"{key_display(key)}:{description.lower()}"
        for key, action, description in available_bindings(state)
        if action not in GLOBAL_ACTIONS
    ]
    if getattr(state, "view", None) == "editor":
        parts.append(EDITOR_LOCAL_HINT)
    parts.append("?:help")
    return "  ".join(parts)


STRUCTURE = """\
─── Littera Structure ───

Work
  └─ Document    (chapter, essay, article)
       └─ Section (scene, argument, part)
            └─ Block   (smallest text unit)

Entities are global concepts; Mentions bind them to blocks.
Alignments link two blocks (e.g. translation).
Reviews are scoped notes about quality or intent."""


EDITING_TRUTH = """\
─── While editing ───

Ctrl+S saves and closes the editor; Esc asks before discarding.
Undo/redo is the text area's own history and only lives as long as
the edit session: once Ctrl+S has saved, the previous text is gone.
Press s (outside the editor) for a snapshot before risky work."""


def help_text(state) -> str:
    """The help overlay: every binding, split into 'here' and 'elsewhere'.

    Generated from BINDINGS so a key can never be added without being
    documented, nor documented without existing.
    """
    here: list[str] = []
    elsewhere: list[str] = []
    for key, action, description in BINDINGS:
        line = f"  {key_display(key):<11}{description}"
        (here if is_available(state, action) else elsewhere).append(line)

    lines = [STRUCTURE, "", "─── Keys available here ───"]
    lines.extend(here or ["  (none)"])
    if elsewhere:
        lines.append("")
        lines.append("─── Keys for other views / selections ───")
        lines.extend(elsewhere)
    lines.append("")
    lines.append(EDITING_TRUTH)
    return "\n".join(lines)
