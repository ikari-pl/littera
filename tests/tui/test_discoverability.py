"""Discoverability: the footer, the hint bars and the help must tell the truth.

littera-qlk / littera-s0j / littera-k2p / littera-89j / littera-1wa.

The unit-level tests drive the real reducer and the real binding table; the
Pilot tests run a real app against the seeded embedded Postgres, because the
footer contents and the editor title only exist once the DOM is mounted.
"""

import asyncio

import pytest
from textual.widgets import Static

from littera.tui import keymap, queries
from littera.tui.app import LitteraApp
from littera.tui.state import (
    AlignmentsSelect,
    EntitiesSelect,
    GotoAlignments,
    GotoEntities,
    GotoReviews,
    OutlinePush,
    OutlineSelect,
    PathElement,
)
from tests.tui.conftest import settle

# =============================================================================
# littera-qlk: availability is view- and selection-dependent
# =============================================================================

def _actions(state) -> set[str]:
    return {action for _key, action, _desc in keymap.available_bindings(state)}


def test_outline_documents_hides_block_and_entity_keys(tui_state, seeded_ids):
    tui_state.dispatch(OutlineSelect(kind="document", item_id=seeded_ids["doc1_id"]))
    available = _actions(tui_state)

    assert "link_entity" not in available, "'l' is a blocks-only key"
    assert "entity_labels" not in available, "'L' is an entities-only key"
    assert "entity_properties" not in available, "'p' is an entities-only key"
    assert "edit_note" not in available
    assert "save" not in available, "Ctrl+S only means something in the editor"
    assert "edit_title" in available
    assert "move_up" in available


def test_outline_blocks_offers_the_block_keys(tui_state, seeded_ids):
    tui_state.dispatch(
        OutlinePush(PathElement(kind="document", id=seeded_ids["doc1_id"], title="d"))
    )
    tui_state.dispatch(
        OutlinePush(PathElement(kind="section", id=seeded_ids["sec1_id"], title="s"))
    )
    tui_state.dispatch(OutlineSelect(kind="block", item_id=seeded_ids["blk1_id"]))
    available = _actions(tui_state)

    assert {"link_entity", "set_language", "show_mentions", "delete_mention"} <= available
    assert "edit_title" not in available, "blocks have no title"


def test_entities_view_offers_label_and_property_keys(tui_state, seeded_ids):
    tui_state.dispatch(GotoEntities())
    tui_state.dispatch(EntitiesSelect(seeded_ids["ent1_id"]))
    available = _actions(tui_state)

    assert {"entity_labels", "entity_properties", "edit_note", "delete_item"} <= available
    assert "link_entity" not in available
    assert "move_up" not in available


def test_alignments_view_hides_outline_keys(tui_state):
    tui_state.dispatch(GotoAlignments())
    available = _actions(tui_state)

    assert "show_gaps" in available
    assert "link_entity" not in available
    assert "edit_title" not in available
    assert "enter" not in available, "alignments have no sub-level to drill into"


def test_delete_needs_a_selection(tui_state):
    tui_state.dispatch(GotoReviews())
    assert "delete_item" not in _actions(tui_state)


def test_check_action_hides_rather_than_disables():
    """In Textual 7, False is "disabled and hidden"; None only greys it out."""
    app = LitteraApp()
    assert app.check_action("link_entity", ()) is False
    assert app.check_action("quit", ()) is True
    # Unknown (Textual's own) actions must not be disabled by our table.
    assert app.check_action("command_palette", ()) is True


# =============================================================================
# littera-s0j: help and hints are generated, so they cannot drift
# =============================================================================

def test_help_documents_every_binding(tui_state):
    text = keymap.help_text(tui_state)
    for key, _action, description in keymap.BINDINGS:
        assert keymap.key_display(key) in text, f"{key} missing from help"
        assert description in text, f"{description} missing from help"


def test_help_states_the_truth_about_undo(tui_state):
    text = keymap.help_text(tui_state)
    assert "Ctrl+S" in text
    assert "undo" in text.lower()


def test_hint_bar_only_names_keys_that_work_here(tui_state, seeded_ids):
    tui_state.dispatch(GotoEntities())
    tui_state.dispatch(EntitiesSelect(seeded_ids["ent1_id"]))
    bar = keymap.hint_bar(tui_state)

    assert "L:labels" in bar
    assert "p:properties" in bar
    assert "l:link entity" not in bar
    assert "?:help" in bar


def test_hint_bar_changes_with_the_outline_level(tui_state, seeded_ids):
    tui_state.dispatch(OutlineSelect(kind="document", item_id=seeded_ids["doc1_id"]))
    documents_bar = keymap.hint_bar(tui_state)

    tui_state.dispatch(
        OutlinePush(PathElement(kind="document", id=seeded_ids["doc1_id"], title="d"))
    )
    tui_state.dispatch(
        OutlinePush(PathElement(kind="section", id=seeded_ids["sec1_id"], title="s"))
    )
    tui_state.dispatch(OutlineSelect(kind="block", item_id=seeded_ids["blk1_id"]))
    blocks_bar = keymap.hint_bar(tui_state)

    assert documents_bar != blocks_bar
    assert "Ctrl+E:edit title" in documents_bar
    assert "l:link entity" in blocks_bar
    assert "l:link entity" not in documents_bar


# =============================================================================
# littera-k2p: no ctrl+shift+letter bindings survive
# =============================================================================

def test_no_ctrl_shift_letter_bindings():
    """Terminal.app and tmux collapse ctrl+shift+l onto ctrl+l, silently."""
    for key, action, _desc in keymap.BINDINGS:
        assert not key.startswith("ctrl+shift+"), (
            f"{key} ({action}) is unreachable in most terminals"
        )


def test_every_binding_has_an_availability_rule():
    """A key with no rule would be shown everywhere again."""
    for _key, action, _desc in keymap.BINDINGS:
        assert action in keymap.AVAILABILITY, f"{action} has no availability rule"


def test_every_binding_has_an_action_method():
    for _key, action, _desc in keymap.BINDINGS:
        assert hasattr(LitteraApp, f"action_{action}"), f"action_{action} is missing"


# =============================================================================
# littera-1wa: undo.py is gone
# =============================================================================

def test_undo_module_is_gone():
    with pytest.raises(ImportError):
        __import__("littera.tui.undo")


def test_no_undo_bindings():
    actions = {action for _key, action, _desc in keymap.BINDINGS}
    assert "undo" not in actions
    assert "redo" not in actions


# =============================================================================
# littera-89j: no raw UUIDs in the editor title or the review detail
# =============================================================================

def test_review_detail_leads_with_severity_and_description(tui_state, seeded_work):
    from littera.tui import actions as tui_actions

    work_id = tui_state.work["work"]["id"]
    review_id = tui_actions.create_review(
        tui_state.db, work_id, "The ending arrives too fast", "high"
    )
    try:
        with tui_state.db.cursor() as cur:
            detail = queries._review_detail(cur, review_id)
        assert detail.splitlines()[0] == "Review [high]: The ending arrives too fast"
        assert str(review_id) not in detail.splitlines()[0]
    finally:
        tui_actions.delete_review(tui_state.db, review_id)


def test_empty_views_say_what_to_press(tui_state):
    assert "Press 'a'" in queries.EMPTY_ENTITIES
    assert "Press 'a'" in queries.EMPTY_ALIGNMENTS
    assert "Press 'a'" in queries.EMPTY_REVIEWS


def test_alignments_empty_state_is_a_call_to_action(tui_state):
    """The seeded work has no alignments, so this is the real empty state."""
    tui_state.dispatch(GotoAlignments())
    queries.refresh_alignments(tui_state)
    if tui_state.alignments.items:
        pytest.skip("work already has alignments")
    assert tui_state.alignments.detail == queries.EMPTY_ALIGNMENTS


def test_selected_alignment_detail_is_not_the_placeholder(tui_state, seeded_ids):
    from littera.tui import actions as tui_actions

    alignment_id = tui_actions.create_alignment(
        tui_state.db, seeded_ids["blk1_id"], seeded_ids["blk2_id"], "translation"
    )
    try:
        tui_state.dispatch(GotoAlignments())
        tui_state.dispatch(AlignmentsSelect(alignment_id))
        queries.refresh_alignments(tui_state)
        assert "Select an alignment" not in tui_state.alignments.detail
    finally:
        tui_actions.delete_alignment(tui_state.db, alignment_id)


# =============================================================================
# Pilot: the footer, the editor title, and Enter outside the outline
# =============================================================================

def _footer_keys(app) -> set[str]:
    from textual.widgets._footer import FooterKey

    return {widget.key for widget in app.screen.query(FooterKey)}


def test_footer_shrinks_to_the_keys_that_work_here(pilot_app):
    """littera-qlk: the footer used to show all 31 bindings in every view."""

    async def body():
        async with pilot_app.run_test(size=(140, 40)) as pilot:
            app = pilot.app
            await settle(pilot)

            documents = _footer_keys(app)
            assert documents, "no footer keys at all"
            assert len(documents) < len(keymap.BINDINGS)
            assert "l" not in documents, "'l' does nothing at the documents level"
            assert "L" not in documents
            assert "ctrl+s" not in documents

            await pilot.press("e")
            await settle(pilot)
            entities = _footer_keys(app)
            assert "L" in entities
            assert "p" in entities
            assert "l" not in entities
            assert entities != documents

    asyncio.run(body())


def test_footer_and_help_agree(pilot_app):
    """littera-s0j: one source for both, so they cannot disagree."""

    async def body():
        async with pilot_app.run_test(size=(140, 40)) as pilot:
            app = pilot.app
            await settle(pilot)

            ours = {key for key, _a, _d in keymap.BINDINGS}
            shown = _footer_keys(app) & ours
            expected = {
                key for key, action, _d in keymap.BINDINGS
                if keymap.is_available(app.state, action)
            }
            assert shown <= expected, shown - expected
            assert shown, "the footer shows none of our keys"

            hint = app.screen.query_one("#hint-bar", Static)
            assert "?:help" in str(hint.content)

    asyncio.run(body())


def test_editor_title_is_readable_not_a_uuid(pilot_app):
    """littera-89j: _start_edit had the title and threw it away."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("enter")
            await settle(pilot)
            await pilot.press("enter")
            await settle(pilot)
            await pilot.press("enter")
            await settle(pilot)
            assert app.state.view == "editor"

            block_id = app.state.edit_session.target.id
            breadcrumb = str(app.screen.query_one("#breadcrumb", Static).content)
            assert block_id not in breadcrumb, f"editor shows a raw uuid: {breadcrumb}"
            assert breadcrumb.startswith("Block ("), breadcrumb

            await pilot.press("escape")
            await settle(pilot)

    asyncio.run(body())


def test_enter_on_an_entity_opens_its_note(pilot_app):
    """The footer promised "Enter"; in entities it did nothing at all."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("e")
            await settle(pilot)
            assert app.state.view == "entities"

            await pilot.press("enter")
            await settle(pilot)

            assert app.state.view == "editor", "Enter on an entity did nothing"
            assert app.state.edit_session.target.kind == "entity_note"
            assert app.state.edit_session.title.startswith("Note: ")

            await pilot.press("escape")
            await settle(pilot)

    asyncio.run(body())


def test_move_at_the_end_of_the_list_says_so(pilot_app):
    """A silent no-op reads as a broken key."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            notifications: list[str] = []
            real_notify = app.notify

            def record(message, **kwargs):
                notifications.append(str(message))
                return real_notify(message, **kwargs)

            app.notify = record
            try:
                await pilot.press("ctrl+up")
                await settle(pilot)
            finally:
                app.notify = real_notify

            assert any("first" in n for n in notifications), notifications

    asyncio.run(body())


def test_help_overlay_lists_the_keys_of_the_current_view(pilot_app):
    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("question_mark")
            await settle(pilot)

            body_widget = app.screen.query_one("#help-body", Static)
            text = str(body_widget.content)
            for _key, _action, description in keymap.BINDINGS:
                assert description in text

            await pilot.press("escape")
            await settle(pilot)

    asyncio.run(body())
