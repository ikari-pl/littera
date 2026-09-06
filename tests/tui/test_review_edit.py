"""TUI review mutations against real embedded Postgres."""

from littera.tui import actions, queries
from littera.tui.state import GotoReviews, ReviewsSelect


def test_update_review_persists(tui_state):
    work_id = tui_state.work.get("work", {}).get("id")
    review_id = actions.create_review(tui_state.db, work_id, "Original", "low")

    actions.update_review(tui_state.db, review_id, description="Revised", severity="high")
    desc, severity = queries.fetch_review(tui_state.db, review_id)

    assert desc == "Revised"
    assert severity == "high"

    tui_state.dispatch(GotoReviews())
    tui_state.dispatch(ReviewsSelect(review_id))
    queries.refresh_reviews(tui_state)
    assert any(item.id == review_id and item.severity == "high" for item in tui_state.reviews.items)
    assert "Revised" in (tui_state.reviews.detail or "")
