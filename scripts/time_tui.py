"""Time the Textual TUI against an existing work (scale spike, littera-496).

    python scripts/time_tui.py WORK_DIR

Drives the real LitteraApp headless with Textual's Pilot, the same way the
TUI tests do. Start Postgres first (`littera mntn-db-start`) so launch time
is the TUI's own.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from textual.widgets import ListView

from littera.tui.app import LitteraApp


async def _until(pilot, predicate, timeout: float = 60.0) -> None:
    deadline = time.perf_counter() + timeout
    while not predicate():
        if time.perf_counter() > deadline:
            raise SystemExit("timed out waiting for the TUI")
        await pilot.pause(0.01)


def _nav(app) -> ListView | None:
    try:
        return app.screen.query_one("#nav", ListView)
    except Exception:  # noqa: BLE001 - not mounted yet
        return None


async def run() -> None:
    app = LitteraApp()
    start = time.perf_counter()
    async with app.run_test(size=(140, 45)) as pilot:
        await _until(pilot, lambda: _nav(app) is not None and len(_nav(app).children) > 0)
        docs = len(_nav(app).children)
        print(f"{'launch -> outline shown':34} {time.perf_counter() - start:7.2f}s  ({docs} documents)")

        t = time.perf_counter()
        for _ in range(50):
            await pilot.press("down")
        await _until(pilot, lambda: _nav(app).index == 50)
        print(f"{'50 x down':34} {time.perf_counter() - t:7.2f}s")

        t = time.perf_counter()
        await pilot.press("enter")
        await _until(pilot, lambda: len(_nav(app).children) != docs)
        sections = len(_nav(app).children)
        print(f"{'enter chapter -> sections':34} {time.perf_counter() - t:7.2f}s  ({sections} sections)")

        t = time.perf_counter()
        await pilot.press("enter")
        await _until(pilot, lambda: len(_nav(app).children) != sections)
        blocks = len(_nav(app).children)
        print(f"{'enter section -> blocks':34} {time.perf_counter() - t:7.2f}s  ({blocks} blocks)")

        # The semantic layer, when the work has one.
        t = time.perf_counter()
        await pilot.press("e")
        await _until(pilot, lambda: app.state.view == "entities" and _nav(app) is not None)
        entities = len(_nav(app).children)
        print(f"{'e -> entities view':34} {time.perf_counter() - t:7.2f}s  ({entities} entities)")

        # Enter on an entity opens its note in the editor, so stay on the list;
        # moving the highlight is what fills the detail pane (labels, mentions).
        if entities > 1:
            t = time.perf_counter()
            await pilot.press("down")
            await _until(pilot, lambda: _nav(app).index == 1)
            print(f"{'down -> next entity detail':34} {time.perf_counter() - t:7.2f}s")

        t = time.perf_counter()
        await pilot.press("R")
        await _until(pilot, lambda: app.state.view == "reviews" and _nav(app) is not None)
        print(
            f"{'R -> reviews view':34} {time.perf_counter() - t:7.2f}s"
            f"  ({len(_nav(app).children)} reviews)"
        )


def main() -> None:
    os.chdir(Path(sys.argv[1]))
    asyncio.run(run())


if __name__ == "__main__":
    main()
