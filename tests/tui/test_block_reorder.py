"""TUI block reordering against real embedded Postgres."""

from littera.tui import actions, queries
from littera.tui.state import OutlinePush, PathElement


def test_move_block_reorders_outline(tui_state, seeded_ids):
    tui_state.dispatch(
        OutlinePush(PathElement(kind="document", id=seeded_ids["doc1_id"], title="Document One"))
    )
    tui_state.dispatch(
        OutlinePush(PathElement(kind="section", id=seeded_ids["sec1_id"], title="Introduction"))
    )
    queries.refresh_outline(tui_state)

    ids_before = [item.id for item in tui_state.outline.items if item.kind == "block"]
    assert seeded_ids["blk1_id"] in ids_before
    assert seeded_ids["blk2_id"] in ids_before
    assert ids_before[0] == seeded_ids["blk1_id"]

    try:
        assert actions.move_item(tui_state.db, "block", seeded_ids["blk1_id"], 2)
        queries.refresh_outline(tui_state)
        ids_after = [item.id for item in tui_state.outline.items if item.kind == "block"]
        assert ids_after[0] == seeded_ids["blk2_id"]
        assert ids_after[1] == seeded_ids["blk1_id"]
    finally:
        actions.move_item(tui_state.db, "block", seeded_ids["blk1_id"], 1)
