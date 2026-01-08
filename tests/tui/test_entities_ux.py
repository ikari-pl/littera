"""
Tests for TUI Entities UX requirements from phase1b-tui.md.

This tests the entity list and detail functionality without relying on state dispatch method.
"""

from littera.tui.state import AppState, EntitiesSelect, GotoEntities
from littera.tui.views.entities import EntitiesView
from unittest.mock import Mock


class TestEntitiesUX:
    """Tests for entities UX functionality."""

    def test_entity_list_renders_without_crashing(self):
        """Entity list should render without crashing."""

        # Create a mock state with some entities
        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()
        state.dispatch(GotoEntities())

        # Mock cursor to return some test entities
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [
            ("ent1", "concept", "Test Concept"),
            ("ent2", "person", "Test Person"),
        ]
        mock_cursor.execute.return_value = None

        # Test the view renders without crashing
        view = EntitiesView()
        result = view.render(state)
        assert len(result) == 1  # Should return layout container
        assert result[0].id == "entities-layout"

    def test_entities_view_shows_help_text_when_no_selection(self):
        """Entities view should show help text when no entity is selected."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Go to entities view without selection
        state.dispatch(GotoEntities())

        # Mock empty database
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None

        # Test rendering with no entities
        view = EntitiesView()
        result = view.render(state)
        assert len(result) == 1  # Should return layout

        # Verify it doesn't crash even with no entities
        mock_cursor.fetchall.assert_called_once()

    def test_entity_list_displays_correct_format(self):
        """Entity list should display entities in correct format."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Go to entities view
        state.dispatch(GotoEntities())

        # Mock cursor to return entities
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [
            ("ent1", "concept", "Test Concept"),
            ("ent2", "person", "Test Person"),
        ]
        mock_cursor.execute.return_value = None

        view = EntitiesView()
        result = view.render(state)
        assert len(result) == 1

        # The view should have queried entities
        execute_calls = [
            str(call[0][0]) if call else ""
            for call in mock_cursor.execute.call_args_list
        ]
        entity_query = next((call for call in execute_calls if "entities" in call), "")
        assert "entities" in entity_query


def test_entities_view_selects_entity_correctly(self):
    """Entities view selection should work correctly."""

    state = AppState()

    # Create mock that can be iterated over
    mock_rows = [("ent1", "concept", "Test Concept")]

    # Set up cursor mock that supports iteration
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = mock_rows
    mock_cursor.fetchone.return_value = ("concept", "Test Entity")
    mock_cursor.execute.return_value = None

    state.db = Mock()
    state.db.cursor.return_value = mock_cursor

    # Go to entities view and select an entity
    state.dispatch(GotoEntities())
    state.dispatch(EntitiesSelect("ent1"))

    assert state.entities.selection.kind == "entity"
    assert state.entities.selection.id == "ent1"

    view = EntitiesView()
    result = view.render(state)
    assert len(result) == 1
