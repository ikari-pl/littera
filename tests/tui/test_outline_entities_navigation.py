"""
Test for navigation between outline and entities without losing context.
"""

from littera.tui.state import (
    AppState,
    EntitiesSelect,
    GotoEntities,
    GotoOutline,
    OutlineSelect,
)
from littera.tui.views.outline import OutlineView
from littera.tui.views.entities import EntitiesView
from unittest.mock import Mock


class TestOutlineEntitiesNavigation:
    """Tests navigation between outline and entities views."""

    def test_navigation_preserves_context(self):
        """Navigation between outline and entities should preserve selection contexts."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        # Set up mock database responses
        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("doc1", "Document 1")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Start in outline view and select a document
        state.dispatch(GotoOutline())
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))

        # Verify outline selection
        assert state.view == "outline"
        assert state.outline.selection.kind == "document"
        assert state.outline.selection.id == "doc1"
        assert state.entities.selection.kind is None  # Entities should be clear

        # Switch to entities view
        state.dispatch(GotoEntities())

        # Verify entities view is active and outline selection preserved
        assert state.view == "entities"
        assert state.outline.selection.kind == "document"  # Outline selection preserved
        assert state.outline.selection.id == "doc1"
        assert state.entities.selection.kind is None  # No entities selection yet

        # Select an entity
        state.dispatch(EntitiesSelect("ent1"))
        assert state.entities.selection.kind == "entity"
        assert state.entities.selection.id == "ent1"

        # Switch back to outline - should restore outline selection
        state.dispatch(GotoOutline())
        assert state.view == "outline"
        assert state.outline.selection.kind == "document"  # Outline selection restored
        assert state.outline.selection.id == "doc1"

        # Switch back to entities - starts fresh (current implementation)
        state.dispatch(GotoEntities())
        assert state.view == "entities"
        assert (
            state.entities.selection.kind is None
        )  # Fresh entities selection (current behavior)
        assert state.outline.selection.kind == "document"  # Outline still preserved

    def test_views_render_without_crashing(self):
        """Both views should render without crashing regardless of selection state."""

        state = AppState()
        state.db = Mock()
        state.db.cursor.return_value = Mock()

        mock_cursor = state.db.cursor.return_value
        mock_cursor.fetchall.return_value = [("doc1", "Document 1")]
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.return_value = None

        # Test outline view renders
        state.dispatch(GotoOutline())
        outline_view = OutlineView()
        outline_result = outline_view.render(state)
        assert len(outline_result) == 1

        # Test entities view renders
        state.dispatch(GotoEntities())
        entities_view = EntitiesView()
        entities_result = entities_view.render(state)
        assert len(entities_result) == 1
