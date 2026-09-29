"""Keyboard-level navigation tests driving a real LitteraApp via Textual Pilot.

These run the app for real (embedded Postgres, real DOM, real key events)
instead of poking AppState directly, because the navigation defects below are
invisible at state level: the reducer is correct, the app's render loop is not.

pytest-asyncio is not a project dependency, so each test drives its own event
loop with asyncio.run().
"""

import asyncio

from tests.tui.conftest import settle


def test_outline_down_moves_selection(pilot_app):
    """littera-gcz: 'down' in the outline must move the selection.

    Today `on_list_view_highlighted` re-renders the whole view, which mounts a
    fresh ListView at index 0 and snaps the highlight (and therefore the
    selection) back to the first item.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            assert app.state is not None
            assert app.state.view == "outline"
            items = list(app.state.outline.items)
            assert len(items) >= 2, "seeded work must have at least two documents"

            first_id = items[0].id
            assert app.state.outline.selection.id == first_id

            await pilot.press("down")
            await settle(pilot)

            assert app.state.outline.selection.id == items[1].id, (
                "one 'down' should select the second outline item, got "
                f"{app.state.outline.selection.id}"
            )

    asyncio.run(body())


def test_outline_down_twice_changes_selection(pilot_app):
    """littera-gcz: two 'down' presses must not leave us on the first item."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            items = list(app.state.outline.items)
            assert len(items) >= 2
            first_id = items[0].id

            await pilot.press("down")
            await settle(pilot)
            await pilot.press("down")
            await settle(pilot)

            assert app.state.outline.selection.id != first_id, (
                "selection still on the first item after two 'down' presses"
            )

    asyncio.run(body())


def test_entities_down_moves_selection(pilot_app):
    """littera-gcz, second view: 'down' in entities must move the selection."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("e")
            await settle(pilot)
            assert app.state.view == "entities"

            items = list(app.state.entities.items)
            assert len(items) >= 2, "seeded work must have at least two entities"
            first_id = items[0].id
            assert app.state.entities.selection.id == first_id

            await pilot.press("down")
            await settle(pilot)

            assert app.state.entities.selection.id == items[1].id, (
                "one 'down' should select the second entity, got "
                f"{app.state.entities.selection.id}"
            )

    asyncio.run(body())


def test_escape_in_entities_returns_to_outline(pilot_app):
    """littera-1pm: 'escape' in entities must go back to the outline.

    Today the ListView auto-highlights the first entity on mount, so the first
    'escape' is consumed clearing that selection and the user stays stuck in
    the entities view.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            await pilot.press("e")
            await settle(pilot)
            assert app.state.view == "entities"

            await pilot.press("escape")
            await settle(pilot)

            assert app.state.view == "outline", (
                "escape from entities left the app in view "
                f"{app.state.view!r}"
            )

    asyncio.run(body())
