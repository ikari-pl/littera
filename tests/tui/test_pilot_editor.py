"""Editor and detail-pane tests driving a real LitteraApp via Textual Pilot.

Same rationale as test_pilot_navigation: both defects below live in the app's
render/key loop, not in the reducer, so only a running app can see them.

pytest-asyncio is not a project dependency, so each test drives its own event
loop with asyncio.run().
"""

import asyncio

from littera.tui import actions, queries
from tests.tui.conftest import settle


async def _drill_to_blocks(pilot) -> None:
    """Outline -> Document One -> Introduction -> blocks."""
    app = pilot.app
    await settle(pilot)
    assert app.state.view == "outline"

    await pilot.press("enter")
    await settle(pilot)
    assert app.state.nav_level == "sections"

    await pilot.press("enter")
    await settle(pilot)
    assert app.state.nav_level == "blocks"
    assert app.state.outline.selection.kind == "block"


def test_escape_in_editor_does_not_silently_lose_text(pilot_app):
    """littera-rcm: escape must not discard typed text without a word.

    Acceptable outcomes: a confirm/discard prompt is shown, the edit session
    stays open, or the text was persisted. Today escape runs ExitEditor
    straight away and the typed characters are gone with no notification.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await _drill_to_blocks(pilot)

            block_id = app.state.outline.selection.id
            _lang, original_text = queries.fetch_block_text(app.state.db, block_id)

            notifications: list[str] = []
            real_notify = app.notify

            def record_notify(message, **kwargs):
                notifications.append(str(message))
                return real_notify(message, **kwargs)

            app.notify = record_notify

            try:
                await pilot.press("enter")
                await settle(pilot)
                assert app.state.view == "editor"

                await pilot.press("Z", "Z", "Z")
                await settle(pilot)
                editor = app.screen.query_one("#editor")
                assert "ZZZ" in editor.text

                await pilot.press("escape")
                await settle(pilot)

                prompted = len(app.screen_stack) > 1
                still_editing = app.state.edit_session is not None
                _lang2, saved_text = queries.fetch_block_text(
                    app.state.db, block_id
                )
                persisted = "ZZZ" in saved_text
                warned = any(
                    "discard" in n.lower() or "unsaved" in n.lower()
                    for n in notifications
                )

                assert prompted or still_editing or persisted or warned, (
                    "escape discarded the typed text silently: "
                    f"view={app.state.view!r} session={app.state.edit_session!r} "
                    f"saved_text={saved_text!r} notifications={notifications!r}"
                )
            finally:
                app.notify = real_notify
                _lang3, current = queries.fetch_block_text(app.state.db, block_id)
                if current != original_text:
                    actions.save_block_text(app.state.db, block_id, original_text)

    asyncio.run(body())


def test_show_mentions_changes_detail_pane(pilot_app):
    """littera-c51: 'M' must put the mention list into the detail pane.

    action_show_mentions writes state.outline.detail and then calls
    _render_view, whose _refresh_data step runs refresh_outline and overwrites
    that detail with the generic block summary before anything is mounted.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await _drill_to_blocks(pilot)

            block_id = app.state.outline.selection.id
            before = {
                m[0] for m in queries.fetch_block_mentions(app.state.db, block_id)
            }
            aristotle = actions.find_entities_by_label(app.state.db, "Aristotle")[0][0]
            actions.link_block_to_entity(app.state.db, block_id, aristotle)
            created = [
                m[0]
                for m in queries.fetch_block_mentions(app.state.db, block_id)
                if m[0] not in before
            ]

            try:
                assert queries.fetch_block_mentions(app.state.db, block_id)

                await pilot.press("M")
                await settle(pilot)

                detail_widget = app.screen.query_one("#detail")
                shown = str(detail_widget.content)

                assert "Mentions for this block:" in shown, (
                    "pressing M did not change the detail pane; it still shows "
                    f"{shown!r}"
                )
                assert "Aristotle" in shown
            finally:
                for mention_id in created:
                    actions.delete_mention(app.state.db, mention_id)

    asyncio.run(body())
