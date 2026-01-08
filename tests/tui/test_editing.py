"""
Test for editing functionality from phase1b-tui.md.

This tests that editing overlay opens for blocks and entities correctly.
"""

from littera.tui.views.editor import EditorView
from littera.tui.state import AppState, EditSession, EditTarget, StartEdit
from unittest.mock import Mock


class TestEditingFunctionality:
    """Tests for editing functionality."""

    def test_editor_view_renders(self):
        """Editor view should render correctly."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Create edit session for block text
        session = EditSession(
            target=EditTarget(kind="block_text", id="blk1"),
            original_text="original block text",
            current_text="edited block text",
        )

        # Set up state with edit session
        state.dispatch(StartEdit())
        state.edit_session = session
        state.active_base = "editor"

        # Editor view should render
        editor_view = EditorView()
        result = editor_view.render(state)
        assert len(result) == 1
        assert result[0].id == "editor-layout"

    def test_editor_view_shows_entity_note_context(self):
        """Editor view should show entity note context."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Create edit session for entity note
        session = EditSession(
            target=EditTarget(kind="entity_note", id="ent1"),
            original_text="original note text",
            current_text="edited note text",
        )

        # Set up state with edit session
        state.dispatch(StartEdit())
        state.edit_session = session
        state.active_base = "editor"

        # Editor view should render with note title
        editor_view = EditorView()
        result = editor_view.render(state)
        assert len(result) == 1
        assert result[0].id == "editor-layout"

        # Should have queried for entity info
        mock_cursor = state.db.cursor.return_value
        mock_cursor.execute.assert_called()

    def test_editor_handles_no_selection_gracefully(self):
        """Editor view should handle no edit session gracefully."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # No edit session
        assert state.edit_session is None
        assert state.active_base != "editor"

        # Editor view should render with no session
        editor_view = EditorView()
        result = editor_view.render(state)
        assert len(result) == 1
        assert result[0].id == "editor-layout"
