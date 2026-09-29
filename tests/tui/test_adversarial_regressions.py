"""Regressions found by adversarially reviewing the 24-defect fix pass.

Each test here corresponds to a defect that was REPRODUCED against the real
app after the original fixes landed.
"""

import pytest

from littera.domain.guards import GuardViolation
from littera.tui import actions
from littera.tui.state import (
    AppState,
    ClearDetail,
    GotoEntities,
    GotoOutline,
    SetDetail,
)

# -------------------------------------------------------------------------
# The TUI could persist an alignment the CLI would refuse.
# -------------------------------------------------------------------------

def test_tui_refuses_same_language_alignment(tui_state, seeded_ids):
    """create_alignment must obey the same rule as `littera alignment add`."""
    db = tui_state.db
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM blocks WHERE language = 'en' ORDER BY created_at LIMIT 1"
        )
        en_block = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO blocks (section_id, block_type, source_text, language) "
            "SELECT section_id, 'paragraph', 'second english block', 'en' "
            "FROM blocks WHERE id = %s RETURNING id",
            (en_block,),
        )
        other_en = str(cur.fetchone()[0])
    db.commit()

    try:
        with pytest.raises(GuardViolation):
            actions.create_alignment(db, en_block, other_en)
        with db.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM block_alignments "
                "WHERE source_block_id = %s AND target_block_id = %s",
                (en_block, other_en),
            )
            assert cur.fetchone()[0] == 0, "same-language alignment was stored"
    finally:
        db.rollback()
        with db.cursor() as cur:
            cur.execute("DELETE FROM blocks WHERE id = %s", (other_en,))
        db.commit()


# -------------------------------------------------------------------------
# A pinned mentions/gaps pane outlived the rows it described.
# -------------------------------------------------------------------------

def test_clear_detail_drops_every_pinned_pane():
    state = AppState()
    state.dispatch(SetDetail("1. concept Stale   S: set surface  D: delete mention"))
    assert state.outline.detail_override is not None

    state.dispatch(ClearDetail())
    assert state.outline.detail_override is None
    assert state.entities.detail_override is None
    assert state.alignments.detail_override is None
    assert state.reviews.detail_override is None


def test_switching_views_drops_a_pinned_pane():
    """Reproduced before the fix: M, e, o left the mentions text pinned."""
    state = AppState()
    state.dispatch(SetDetail("mentions of this block"))
    state.dispatch(GotoEntities())
    state.dispatch(GotoOutline())

    assert state.outline.detail_override is None, "stale pane survived a view switch"
