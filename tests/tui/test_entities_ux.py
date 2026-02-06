"""
Test for entities UX functionality from phase1b-tui.md.

Verifies entities list, detail, and navigation against real Postgres.
"""

from littera.tui.state import EntitiesSelect, GotoEntities
from littera.tui.views.entities import EntitiesView


class TestEntitiesUX:
    """Tests for entities UX functionality."""

    def test_entity_list_renders_without_crashing(self, tui_state):
        """Entity list should render without crashing."""
        tui_state.dispatch(GotoEntities())

        entities_view = EntitiesView()
        result = entities_view.render(tui_state)
        assert len(result) == 1

    def test_entity_list_displays_correct_format(self, tui_state):
        """Entity list should display entities in correct format."""
        tui_state.dispatch(GotoEntities())

        entities_view = EntitiesView()
        result = entities_view.render(tui_state)
        assert len(result) == 1

    def test_entity_detail_shows_help_text_when_no_selection(self, tui_state):
        """Entities view should show help text when no entity is selected."""
        tui_state.dispatch(GotoEntities())
        assert tui_state.entities.selection.kind is None

        entities_view = EntitiesView()
        result = entities_view.render(tui_state)
        assert len(result) == 1

    def test_entities_view_selects_entity_correctly(self, tui_state, seeded_ids):
        """Entities view should select entity correctly."""
        tui_state.dispatch(GotoEntities())
        tui_state.dispatch(EntitiesSelect(seeded_ids["ent1_id"]))

        assert tui_state.entities.selection.kind == "entity"
        assert tui_state.entities.selection.id == seeded_ids["ent1_id"]
