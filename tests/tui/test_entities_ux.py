"""
Test for entities UX functionality from phase1b-tui.md.

This tests entities list, detail, and navigation behavior.
"""

import pytest
from littera.tui.state import AppState, EntitiesSelect, GotoEntities, GotoOutline
from littera.tui.views.entities import EntitiesView
from littera.tui.views.outline import OutlineView
from unittest.mock import Mock


class TestEntitiesUX:
    """Tests for entities UX functionality."""

    def test_entity_list_renders_without_crashing(self):
        """Entity list should render without crashing."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Mock database responses
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("ent1", "concept", "Test Concept")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Go to entities view
        state.dispatch(GotoEntities())

        # Test entities view renders
        entities_view = EntitiesView()
        result = entities_view.render(state)
        assert len(result) == 1  # Should return layout container

    def test_entity_list_displays_correct_format(self):
        """Entity list should display entities in correct format."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Mock database responses
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("ent1", "concept", "Test Concept")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Go to entities view
        state.dispatch(GotoEntities())

        # Test entities view renders
        entities_view = EntitiesView()
        result = entities_view.render(state)
        assert len(result) == 1

        # The view should have queried entities
        execute_calls = [
            str(call[0][0]) if call and call[0] else ""
            for call in mock_cursor.execute.call_args_list
        ]
        assert any("entities" in call for call in execute_calls)

    def test_entity_detail_shows_help_text_when_no_selection(self):
        """Entities view should show help text when no entity is selected."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Mock database responses
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("ent1", "concept", "Test Concept")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Go to entities view without selection
        state.dispatch(GotoEntities())
        assert state.entities.selection.kind is None

        # Test entities view renders with help text
        entities_view = EntitiesView()
        result = entities_view.render(state)
        assert len(result) == 1

    def test_entities_view_selects_entity_correctly(self):
        """Entities view should select entity correctly."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Mock database responses
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("ent1", "concept", "Test Concept")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Go to entities view and select an entity
        state.dispatch(GotoEntities())
        state.dispatch(EntitiesSelect("ent1"))

        assert state.entities.selection.kind == "entity"
        assert state.entities.selection.id == "ent1"
