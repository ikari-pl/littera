"""
Test for navigation between outline and entities views.

Verifies context preservation between views against real Postgres.
"""

from littera.tui.state import OutlineSelect, GotoOutline
from littera.tui.state import EntitiesSelect, GotoEntities
from littera.tui.views.outline import OutlineView
from littera.tui.views.entities import EntitiesView


class TestOutlineEntitiesNavigation:
    """Tests navigation between outline and entities views."""

    def test_navigation_preserves_context(self, tui_state, seeded_ids):
        """Navigation between outline and entities should preserve selection contexts."""
        tui_state.dispatch(GotoOutline())
        tui_state.dispatch(
            OutlineSelect(kind="document", item_id=seeded_ids["doc1_id"])
        )

        assert tui_state.view == "outline"
        assert tui_state.outline.selection.kind == "document"
        assert tui_state.outline.selection.id == seeded_ids["doc1_id"]
        assert tui_state.entities.selection.kind is None

        tui_state.dispatch(GotoEntities())

        assert tui_state.view == "entities"
        assert tui_state.outline.selection.kind == "document"
        assert tui_state.outline.selection.id == seeded_ids["doc1_id"]
        assert tui_state.entities.selection.kind is None

        tui_state.dispatch(EntitiesSelect(seeded_ids["ent1_id"]))
        assert tui_state.entities.selection.kind == "entity"
        assert tui_state.entities.selection.id == seeded_ids["ent1_id"]

        tui_state.dispatch(GotoOutline())
        assert tui_state.view == "outline"
        assert tui_state.outline.selection.kind == "document"
        assert tui_state.outline.selection.id == seeded_ids["doc1_id"]

        tui_state.dispatch(GotoEntities())
        assert tui_state.view == "entities"
        assert tui_state.entities.selection.kind == "entity"
        assert tui_state.entities.selection.id == seeded_ids["ent1_id"]
        assert tui_state.outline.selection.kind == "document"

    def test_views_render_without_crashing(self, tui_state):
        """Both views should render without crashing regardless of selection state."""
        tui_state.dispatch(GotoOutline())
        outline_view = OutlineView()
        outline_result = outline_view.render(tui_state)
        assert len(outline_result) == 1

        tui_state.dispatch(GotoEntities())
        entities_view = EntitiesView()
        entities_result = entities_view.render(tui_state)
        assert len(entities_result) == 1
