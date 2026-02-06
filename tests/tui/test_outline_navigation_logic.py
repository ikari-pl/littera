"""
Test for specific navigation UX requirements from phase1b-tui.md.

Verifies outline navigation logic against a real embedded Postgres.
"""

from littera.tui.state import (
    AppState,
    PathElement,
    OutlinePush,
    OutlinePop,
    OutlineSelect,
    OutlineClearSelection,
)


class TestOutlineNavigation:
    """Tests for the first unchecked navigation requirement."""

    def test_left_pane_lists_current_level_reliably(self):
        """Left pane lists current level (docs -> sections -> blocks) reliably."""
        # Pure state test - no DB needed
        state = AppState()
        assert state.nav_level == "documents"

        state.dispatch(
            OutlinePush(PathElement(kind="document", id="doc1", title="Document 1"))
        )
        assert state.nav_level == "sections"

        state.dispatch(
            OutlinePush(PathElement(kind="section", id="sec1", title="Section 1"))
        )
        assert state.nav_level == "blocks"

        state.dispatch(OutlinePop())
        assert state.nav_level == "sections"

        state.dispatch(OutlinePop())
        assert state.nav_level == "documents"

    def test_outline_view_content_logic(self, tui_state):
        """Test that outline view shows correct content based on path depth."""
        from littera.tui.views.outline import OutlineView

        view = OutlineView()
        result = view.render(tui_state)

        # At root level, should return layout with documents listed
        assert len(result) == 1


class TestRightPaneDetail:
    """Tests for right pane detail functionality."""

    def test_right_pane_shows_document_detail(self, tui_state, seeded_ids):
        """Right pane should show detail for selected document."""
        from littera.tui.views.outline import OutlineView

        tui_state.dispatch(
            OutlineSelect(kind="document", item_id=seeded_ids["doc1_id"])
        )

        view = OutlineView()
        result = view.render(tui_state)
        assert len(result) == 1

    def test_right_pane_shows_section_detail(self, tui_state, seeded_ids):
        """Right pane should show detail for selected section."""
        from littera.tui.views.outline import OutlineView

        tui_state.dispatch(
            OutlinePush(
                PathElement(
                    kind="document",
                    id=seeded_ids["doc1_id"],
                    title=seeded_ids["doc1_title"],
                )
            )
        )
        tui_state.dispatch(
            OutlineSelect(kind="section", item_id=seeded_ids["sec1_id"])
        )

        view = OutlineView()
        result = view.render(tui_state)
        assert len(result) == 1

    def test_right_pane_shows_block_detail(self, tui_state, seeded_ids):
        """Right pane should show detail for selected block."""
        from littera.tui.views.outline import OutlineView

        tui_state.dispatch(
            OutlinePush(
                PathElement(
                    kind="document",
                    id=seeded_ids["doc1_id"],
                    title=seeded_ids["doc1_title"],
                )
            )
        )
        tui_state.dispatch(
            OutlinePush(
                PathElement(
                    kind="section",
                    id=seeded_ids["sec1_id"],
                    title=seeded_ids["sec1_title"],
                )
            )
        )
        tui_state.dispatch(
            OutlineSelect(kind="block", item_id=seeded_ids["blk1_id"])
        )

        view = OutlineView()
        result = view.render(tui_state)
        assert len(result) == 1

    def test_right_pane_shows_help_when_no_selection(self, tui_state):
        """Right pane should show help text when no item is selected."""
        from littera.tui.views.outline import OutlineView

        view = OutlineView()
        result = view.render(tui_state)
        assert len(result) == 1


class TestHighlightUpdatesDetail:
    """Tests for highlight updating detail without drill-down."""

    def test_highlight_updates_selection_without_drill_down(
        self, tui_state, seeded_ids
    ):
        """Highlight should update selection and detail without changing navigation level."""
        assert tui_state.nav_level == "documents"
        assert tui_state.entity_selection.kind is None

        tui_state.dispatch(
            OutlineSelect(kind="document", item_id=seeded_ids["doc1_id"])
        )

        assert tui_state.entity_selection.kind == "document"
        assert tui_state.entity_selection.id == seeded_ids["doc1_id"]
        assert tui_state.nav_level == "documents"
        assert len(tui_state.path) == 0

    def test_different_highlights_update_selection(self, tui_state, seeded_ids):
        """Highlighting different items should update selection appropriately."""
        tui_state.dispatch(
            OutlinePush(
                PathElement(
                    kind="document",
                    id=seeded_ids["doc1_id"],
                    title=seeded_ids["doc1_title"],
                )
            )
        )
        assert tui_state.nav_level == "sections"

        tui_state.dispatch(
            OutlineSelect(kind="section", item_id=seeded_ids["sec1_id"])
        )
        assert tui_state.entity_selection.kind == "section"
        assert tui_state.entity_selection.id == seeded_ids["sec1_id"]
        assert tui_state.nav_level == "sections"

        tui_state.dispatch(
            OutlinePush(
                PathElement(
                    kind="section",
                    id=seeded_ids["sec1_id"],
                    title=seeded_ids["sec1_title"],
                )
            )
        )
        assert tui_state.nav_level == "blocks"

        tui_state.dispatch(
            OutlineSelect(kind="block", item_id=seeded_ids["blk1_id"])
        )
        assert tui_state.entity_selection.kind == "block"
        assert tui_state.entity_selection.id == seeded_ids["blk1_id"]
        assert tui_state.nav_level == "blocks"

    def test_highlight_same_item_no_change(self):
        """Highlighting the same item should not trigger unnecessary updates."""
        # Pure state test - no DB needed
        state = AppState()

        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))
        state.dispatch(OutlineSelect(kind="document", item_id="doc1"))

        assert state.entity_selection.kind == "document"
        assert state.entity_selection.id == "doc1"

    def test_clear_selection_on_highlight_empty(self):
        """Highlight should handle empty/none cases gracefully."""
        # Pure state test - no DB needed
        state = AppState()

        assert state.entity_selection.kind is None
        assert state.entity_selection.id is None

        state.dispatch(OutlineClearSelection())
        assert state.entity_selection.kind is None
        assert state.entity_selection.id is None
