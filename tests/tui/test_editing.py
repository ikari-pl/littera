"""
Test for editing functionality from phase1b-tui.md.

Verifies that the editing overlay opens for blocks and entities correctly.
EditorView.render() doesn't query the DB, but we still provide a real
connection to eliminate all Mock usage per MANIFESTO.
"""

from littera.tui.views.editor import EditorView
from littera.tui.state import EditSession, EditTarget, StartEdit


class TestEditingFunctionality:
    """Tests for editing functionality."""

    def test_editor_view_renders(self, tui_state):
        """Editor view should render correctly."""
        tui_state.dispatch(
            StartEdit(
                target=EditTarget(kind="block_text", id="blk1"),
                text="original block text",
                return_to="outline",
            )
        )

        editor_view = EditorView()
        result = editor_view.render(tui_state)
        assert len(result) == 1
        assert result[0].id == "editor_layout"

    def test_editor_view_shows_entity_note_context(self, tui_state):
        """Editor view should show entity note context."""
        tui_state.dispatch(
            StartEdit(
                target=EditTarget(kind="entity_note", id="ent1"),
                text="original note text",
                return_to="entities",
            )
        )

        editor_view = EditorView()
        result = editor_view.render(tui_state)
        assert len(result) == 1
        assert result[0].id == "editor_layout"
        assert tui_state.edit_session is not None
        assert tui_state.edit_session.target.kind == "entity_note"

    def test_editor_handles_no_selection_gracefully(self, tui_state):
        """Editor view should handle no edit session gracefully."""
        assert tui_state.edit_session is None
        assert tui_state.active_base != "editor"

        editor_view = EditorView()
        result = editor_view.render(tui_state)
        assert len(result) == 1
        assert result[0].id == "editor_layout"
