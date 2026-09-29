"""Pushed-dialog isolation tests driving a real LitteraApp via Textual Pilot.

pytest-asyncio is not a project dependency, so each test drives its own event
loop with asyncio.run().
"""

import asyncio

from tests.tui.conftest import settle


def test_block_picker_does_not_poison_alignment_selection(pilot_app):
    """littera-37t: a pushed picker must not be mistaken for the nav list.

    PickListDialog is a Screen, so its ListView.Highlighted bubbles up to the
    App. The App used to accept the picker's "opt-0" item id as an alignment
    id, dispatch AlignmentsSelect("opt-0"), and then hand that string to a
    `WHERE a.id = %s` against a uuid column -- which aborts the transaction and
    leaves every later query failing.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("A")
            await settle(pilot)
            assert app.state.view == "alignments"

            await pilot.press("a")
            await settle(pilot)

            # The picker is open on top of the alignments view.
            assert len(app.screen_stack) > 1, "block picker did not open"

            selection = app.state.alignments.selection
            assert selection.id != "opt-0"
            assert selection.id is None, (
                f"picker highlight leaked into the base view: {selection!r}"
            )

            # The connection must still be usable: a poisoned transaction would
            # raise InFailedSqlTransaction here.
            with app.state.db.cursor() as cur:
                cur.execute("SELECT count(*) FROM blocks")
                assert cur.fetchone()[0] >= 1

    asyncio.run(body())


def test_quit_from_dirty_editor_asks_first(pilot_app):
    """littera-rcm: ctrl+q must not throw away unsaved editor text."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("enter")
            await settle(pilot)
            await pilot.press("enter")
            await settle(pilot)
            assert app.state.nav_level == "blocks"

            await pilot.press("enter")
            await settle(pilot)
            assert app.state.view == "editor"

            await pilot.press("Z", "Z", "Z")
            await settle(pilot)

            await pilot.press("ctrl+q")
            await settle(pilot)

            assert app.is_running, "ctrl+q quit with unsaved text and no prompt"
            assert len(app.screen_stack) > 1, "no discard prompt was shown"

            # Answer "no" so the app is left in a clean state.
            await pilot.press("n")
            await settle(pilot)
            assert app.state.view == "editor"

    asyncio.run(body())


def test_switching_view_from_editor_keeps_view_and_base_consistent(pilot_app):
    """littera-rcm: GotoX must be applied after ExitEditor, not before.

    ExitEditor restores `view` from the editor overlay's return_to, so
    dispatching GotoEntities first left `view == "outline"` while
    `active_base == "entities"`.

    The editor swallows printable keys, so this route is the footer click:
    the action is invoked directly, exactly as Textual invokes it.
    """

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

            # Nothing typed -> no prompt, the switch happens straight away.
            app.action_entities()
            await settle(pilot)

            assert app.state.edit_session is None
            assert app.state.view == "entities"
            assert app.state.active_base == "entities"

    asyncio.run(body())
