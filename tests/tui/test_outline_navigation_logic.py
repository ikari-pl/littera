"""
Test for specific navigation UX requirements from phase1b-tui.md.

This test verifies that outline navigation logic without requiring a full database setup.
"""

from littera.tui.state import AppState, PathElement, OutlinePush, OutlinePop, OutlineSelect


class TestOutlineNavigation:
    """Tests for the first unchecked navigation requirement."""

    def test_left_pane_lists_current_level_reliably(self):
        """Left pane lists current level (docs → sections → blocks) reliably."""
        
        # Initial state should be at documents level
        state = AppState()
        assert state.nav_level == "documents"
        
        # After drilling into a document, should be at sections level
        state.dispatch(OutlinePush(
            PathElement(kind="document", id="doc1", title="Document 1")
        ))
        assert state.nav_level == "sections"
        
        # After drilling into a section, should be at blocks level
        state.dispatch(OutlinePush(
            PathElement(kind="section", id="sec1", title="Section 1")
        ))
        assert state.nav_level == "blocks"
        
        # After popping back to document, should be at sections level
        state.dispatch(OutlinePop())
        assert state.nav_level == "sections"
        
        # After popping all the way back, should be at documents level
        state.dispatch(OutlinePop())
        assert state.nav_level == "documents"

    def test_outline_view_content_logic(self):
        """Test that outline view shows correct content based on path depth."""
        from littera.tui.views.outline import OutlineView
        from unittest.mock import Mock
        
        # Create a mock state with database cursor
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock cursor behavior
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        
        view = OutlineView()
        
        # At root level, should query documents
        view.render(state)
        
        # Verify that right queries would be made
        for call_args, _ in mock_cursor.execute.call_args_list:
            query = call_args[0] if call_args else ""
            assert "documents" in query or "sections" in query or "blocks" in query


class TestRightPaneDetail:
    """Tests for right pane detail functionality."""

    def test_right_pane_shows_document_detail(self):
        """Right pane should show detail for selected document."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock document data
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []  # No sections
        mock_cursor.fetchone.return_value = ("Test Document",)  # Document title
        mock_cursor.execute.return_value = None
        
        # Select a document
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))
        
        # Import here to avoid stub issues
        from littera.tui.views.outline import OutlineView
        view = OutlineView()
        view.render(state)
        
        # Should have queried document title and section count
        execute_calls = [str(call[0][0]) for call in mock_cursor.execute.call_args_list]
        document_queries = [call for call in execute_calls if "documents" in call]
        assert len(document_queries) > 0

    def test_right_pane_shows_section_detail(self):
        """Right pane should show detail for selected section."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock section data
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []  # No blocks
        mock_cursor.fetchone.return_value = ("Test Section",)  # Section title
        mock_cursor.execute.return_value = None
        
        # Select a section
        state.dispatch(OutlineSelect(kind="section", item_id="sec1"))
        
        # Import here to avoid stub issues
        from littera.tui.views.outline import OutlineView
        view = OutlineView()
        view.render(state)
        
        # Should have queried section title and block count
        execute_calls = [str(call[0][0]) for call in mock_cursor.execute.call_args_list]
        section_queries = [call for call in execute_calls if "sections" in call]
        assert len(section_queries) > 0

    def test_right_pane_shows_block_detail(self):
        """Right pane should show detail for selected block."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock block data
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = ("en", "This is test block content")  # Block language and text
        mock_cursor.execute.return_value = None
        
        # Select a block
        state.dispatch(OutlineSelect(kind="block", item_id="blk1"))
        
        # Import here to avoid stub issues
        from littera.tui.views.outline import OutlineView
        view = OutlineView()
        view.render(state)
        
        # Should have queried block language and text
        execute_calls = [str(call[0][0]) for call in mock_cursor.execute.call_args_list]
        block_queries = [call for call in execute_calls if "blocks" in call]
        assert len(block_queries) > 0

    def test_right_pane_shows_help_when_no_selection(self):
        """Right pane should show help text when no item is selected."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock empty documents list
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None
        
        # No selection
        # Import here to avoid stub issues
        from littera.tui.views.outline import OutlineView
        view = OutlineView()
        result = view.render(state)
        
        # Should return layout with help text in detail pane
        assert len(result) == 1


class TestHighlightUpdatesDetail:
    """Tests for highlight updating detail without drill-down."""

    def test_highlight_updates_selection_without_drill_down(self):
        """Highlight should update selection and detail without changing navigation level."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        # Mock data
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("doc1", "Test Document")]
        mock_cursor.fetchone.return_value = ("Test Document",)
        mock_cursor.execute.return_value = None
        
        # Initially at documents level
        assert state.nav_level == "documents"
        assert state.entity_selection.kind is None
        
        # Simulate list highlight event
        # This tests the logic that would be called by on_list_view_highlighted
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))
        
        # Selection should be updated
        assert state.entity_selection.kind == "document"
        assert state.entity_selection.id == "doc1"
        
        # Navigation level should NOT change (no drill-down)
        assert state.nav_level == "documents"
        assert len(state.path) == 0

    def test_different_highlights_update_selection(self):
        """Highlighting different items should update selection appropriately."""
        from unittest.mock import Mock
        
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = ("Mock Title",)
        mock_cursor.execute.return_value = None
        
        # Drill down to sections level
        state.dispatch(OutlinePush(PathElement(kind="document", id="doc1", title="Doc 1")))
        assert state.nav_level == "sections"
        
        # Highlight a section
        state.dispatch(OutlineSelect(kind="section", item_id="sec1"))
        assert state.entity_selection.kind == "section"
        assert state.entity_selection.id == "sec1"
        assert state.nav_level == "sections"  # Still at sections level
        
        # Drill down to blocks level  
        state.dispatch(OutlinePush(PathElement(kind="section", id="sec1", title="Sec 1")))
        assert state.nav_level == "blocks"
        
        # Highlight a block
        state.dispatch(OutlineSelect(kind="block", item_id="blk1"))
        assert state.entity_selection.kind == "block"
        assert state.entity_selection.id == "blk1"
        assert state.nav_level == "blocks"  # Still at blocks level

    def test_highlight_same_item_no_change(self):
        """Highlighting the same item should not trigger unnecessary updates."""
        state = AppState()
        
        # Select an item
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))
        
        # Select the same item again (should not cause issues)
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))
        
        # Selection should remain the same
        assert state.entity_selection.kind == "document"
        assert state.entity_selection.id == "doc1"

    def test_clear_selection_on_highlight_empty(self):
        """Highlight should handle empty/none cases gracefully."""
        state = AppState()
        
        # Initially no selection
        assert state.entity_selection.kind is None
        assert state.entity_selection.id is None
        
        # Clear selection should work
        from littera.tui.state import OutlineClearSelection
        state.dispatch(OutlineClearSelection())
        assert state.entity_selection.kind is None
        assert state.entity_selection.id is None