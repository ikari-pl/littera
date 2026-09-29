"""Pilot tests for the destructive and linking paths of the running app.

These defects live in the app's dialog wiring, not in actions.py, so only a
running app can see them.

pytest-asyncio is not a project dependency, so each test drives its own event
loop with asyncio.run().
"""

import asyncio
import uuid

from littera.tui import actions, queries
from littera.tui.views.input_dialog import PickListDialog, SnapshotConfirmDialog
from tests.tui.conftest import settle


async def _drill_to_blocks(pilot) -> None:
    app = pilot.app
    await settle(pilot)
    await pilot.press("enter")
    await settle(pilot)
    await pilot.press("enter")
    await settle(pilot)
    assert app.state.nav_level == "blocks"


def test_delete_confirm_names_what_it_destroys(pilot_app):
    """littera-4ib: "This cannot be undone." never said what "this" includes."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await _drill_to_blocks(pilot)

            block_id = app.state.outline.selection.id
            entity_id = actions.create_entity(
                app.state.db, "concept", f"Confirm {uuid.uuid4()}"
            )
            actions.link_block_to_entity(app.state.db, block_id, entity_id)
            try:
                await pilot.press("d")
                await settle(pilot)

                screen = app.screen
                assert isinstance(screen, SnapshotConfirmDialog), (
                    f"delete did not open the destructive confirm: {screen!r}"
                )
                message = screen._message
                assert "1 mention" in message, (
                    f"confirm text hides the cascade: {message!r}"
                )
                assert "snapshot" in " ".join(
                    b.id or "" for b in screen.query("Button")
                ) or any(
                    (b.id or "") == "snapshot" for b in screen.query("Button")
                ), "no snapshot-first option offered"

                await pilot.press("escape")
                await settle(pilot)

                # Nothing was deleted.
                assert queries.fetch_block_mentions(app.state.db, block_id)
            finally:
                for mention_id, *_ in queries.fetch_block_mentions(
                    app.state.db, block_id
                ):
                    actions.delete_mention(app.state.db, mention_id)
                actions.delete_entity(app.state.db, entity_id)

    asyncio.run(body())


def test_linking_an_unknown_name_does_not_create_an_entity(pilot_app):
    """littera-d2p: 'l' used to silently insert a concept entity."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await _drill_to_blocks(pilot)

            name = f"Ghost {uuid.uuid4()}"

            await pilot.press("l")
            await settle(pilot)
            for char in name:
                await pilot.press(char if char != " " else "space")
            await pilot.press("enter")
            await settle(pilot)

            assert isinstance(app.screen, PickListDialog), (
                f"no explicit choice was offered: {app.screen!r}"
            )
            with app.state.db.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM entities WHERE canonical_label = %s", (name,)
                )
                assert cur.fetchone()[0] == 0, "entity was auto-created"

            await pilot.press("escape")
            await settle(pilot)

            with app.state.db.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM entities WHERE canonical_label = %s", (name,)
                )
                assert cur.fetchone()[0] == 0

    asyncio.run(body())


def test_mention_deletion_is_keyed_by_id_not_by_position(pilot_app):
    """littera-5w7: the old prompt took a 1-based index into a stale snapshot.

    The key moved from ctrl+shift+d to D (littera-k2p): Textual has no
    ctrl+shift+letter sequence in most terminals, so the old binding could
    never fire outside a CSI-u/kitty terminal.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await _drill_to_blocks(pilot)

            block_id = app.state.outline.selection.id
            entity_id = actions.create_entity(
                app.state.db, "concept", f"Pick {uuid.uuid4()}"
            )
            actions.link_block_to_entity(app.state.db, block_id, entity_id)
            try:
                await pilot.press("D")
                await settle(pilot)

                screen = app.screen
                assert isinstance(screen, PickListDialog), (
                    f"mention deletion still asks for a number: {screen!r}"
                )
                option_ids = [oid for oid, _label in screen._options]
                existing = {
                    m[0] for m in queries.fetch_block_mentions(app.state.db, block_id)
                }
                assert set(option_ids) == existing, (
                    "picker options are not mention ids"
                )

                await pilot.press("escape")
                await settle(pilot)
            finally:
                for mention_id, *_ in queries.fetch_block_mentions(
                    app.state.db, block_id
                ):
                    actions.delete_mention(app.state.db, mention_id)
                actions.delete_entity(app.state.db, entity_id)

    asyncio.run(body())


def test_snapshot_binding_writes_a_file(pilot_app, seeded_work):
    """littera-ejj: snapshot was CLI-only, though the TUI is where deletes happen."""
    workdir, _cfg, _pg_cfg = seeded_work

    async def body():
        async with pilot_app.run_test() as pilot:
            await settle(pilot)
            snap_dir = workdir / ".littera" / "snapshots"
            before = set(snap_dir.glob("*.json")) if snap_dir.exists() else set()

            await pilot.press("s")
            await settle(pilot)

            after = set(snap_dir.glob("*.json"))
            created = after - before
            assert created, "pressing s wrote no snapshot"
            for path in created:
                path.unlink()

    asyncio.run(body())
