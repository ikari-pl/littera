"""Failure paths must be visible and survivable.

Covers:
- littera-u9w: a failed statement must roll back, notify, and leave the
  connection usable instead of poisoning it for every later keystroke.
- littera-8a0: the TUI applies pending migrations on boot.
- littera-9gg: the TUI owns the Postgres lease while it runs.
- littera-d1k: launching outside a work exits instead of rendering a dead shell.
- littera-nru: the recovery dialog never auto-focuses the destructive button.

Real embedded Postgres throughout (project rule: no mocks for core behavior).
pytest-asyncio is not a project dependency, so each test drives its own loop
with asyncio.run(), as the other pilot tests do.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import psycopg

from littera.tui import actions, queries
from littera.tui.app import DB_FAILED, LitteraApp
from littera.tui.views.input_dialog import RecoveryDialog
from tests.tui.conftest import settle


def _capture_notifications(app) -> list[tuple[str, dict]]:
    """Replace app.notify with a recorder. Returns the list of (message, kwargs)."""
    seen: list[tuple[str, dict]] = []

    def fake_notify(message, **kwargs):
        seen.append((str(message), kwargs))

    app.notify = fake_notify
    return seen


# =============================================================================
# littera-u9w — zombie connections
# =============================================================================

def test_failed_write_rolls_back_notifies_and_leaves_connection_usable(pilot_app):
    """A foreign-key violation must not turn the connection into a zombie.

    Before the fix, actions.create_section had no except clause, so psycopg
    left the connection in InFailedSqlTransaction and every later statement
    raised too — the app died several keystrokes later in unrelated code.
    """

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)
            assert app.state is not None

            seen = _capture_notifications(app)

            orphan_document = str(uuid.uuid4())  # no such document row
            result = app._db(
                actions.create_section,
                app.state.db,
                orphan_document,
                "Orphan section",
            )

            assert result is DB_FAILED
            assert seen, "the user was not told anything"
            assert seen[-1][1].get("severity") == "error"

            # The connection is not poisoned: plain reads work...
            with app.state.db.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1

            # ...and so does the next real write.
            entity_id = app._db(
                actions.create_entity, app.state.db, "concept", "After failure"
            )
            assert entity_id is not DB_FAILED
            with app.state.db.cursor() as cur:
                cur.execute(
                    "SELECT canonical_label FROM entities WHERE id = %s", (entity_id,)
                )
                assert cur.fetchone()[0] == "After failure"
                cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
            app.state.db.commit()

    asyncio.run(body())


def test_missing_row_is_reported_not_swallowed(pilot_app):
    """LookupError from a fetch_* query reaches the user instead of vanishing."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)
            seen = _capture_notifications(app)

            result = app._db(
                queries.fetch_review,
                app.state.db,
                str(uuid.uuid4()),
                label="Read review",
            )
            assert result is DB_FAILED
            assert seen and seen[-1][1].get("severity") == "error"

    asyncio.run(body())


def test_render_survives_a_database_error(pilot_app):
    """A failing refresh shows the error in the detail pane instead of going dark."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)
            seen = _capture_notifications(app)

            original = queries.refresh_outline

            def boom(state):
                raise psycopg.errors.UndefinedTable("relation does not exist")

            queries.refresh_outline = boom
            try:
                app._render_view()
                await settle(pilot)
            finally:
                queries.refresh_outline = original

            assert seen and seen[-1][1].get("severity") == "error"
            override = app.state.outline.detail_override
            assert override is not None and "Database error" in override

            # The app is still alive and the connection is usable.
            assert app.is_running
            with app.state.db.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1

    asyncio.run(body())


# =============================================================================
# littera-8a0 — the TUI runs migrations
# =============================================================================

def test_tui_boot_applies_pending_migrations(seeded_work, monkeypatch):
    """Opening the TUI against a work whose schema_version is behind migrates it."""
    workdir, _cfg, pg_cfg = seeded_work

    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(version) FROM schema_version")
        latest = cur.fetchone()[0]
        assert latest and latest > 0
        cur.execute("DELETE FROM schema_version WHERE version = %s", (latest,))
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        assert cur.fetchone()[0] == latest - 1
    conn.commit()
    conn.close()

    monkeypatch.chdir(workdir)
    app = LitteraApp()

    async def body():
        async with app.run_test() as pilot:
            await settle(pilot)
            assert app.state is not None

    asyncio.run(body())

    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        assert cur.fetchone()[0] == latest, "the TUI did not apply pending migrations"
    conn.close()


# =============================================================================
# littera-9gg — the TUI owns the Postgres lease
# =============================================================================

def test_tui_holds_the_pg_lease_while_running(seeded_work, monkeypatch):
    """A CLI lease watcher must not stop Postgres underneath a live TUI."""
    workdir, _cfg, _pg_cfg = seeded_work
    lease_path = workdir / ".littera" / "pg_lease.json"

    # A CLI command has just run and left a lease about to expire.
    lease_path.write_text(json.dumps({"version": 1, "expires_at": time.time() + 1}))

    monkeypatch.chdir(workdir)
    monkeypatch.setenv("LITTERA_PG_LEASE_SECONDS", "60")

    app = LitteraApp()

    async def body():
        async with app.run_test() as pilot:
            await settle(pilot)
            assert app.state is not None
            lease = json.loads(lease_path.read_text())
            assert lease["expires_at"] > time.time() + 30, (
                "the TUI did not take ownership of the lease"
            )

    try:
        asyncio.run(body())
    finally:
        lease_path.unlink(missing_ok=True)


# =============================================================================
# littera-d1k — no dead shell outside a work
# =============================================================================

def test_tui_outside_a_work_exits_instead_of_rendering_a_dead_shell(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    app = LitteraApp()

    async def body():
        async with app.run_test() as pilot:
            await settle(pilot)

    asyncio.run(body())

    assert app.state is None
    assert app.return_code == 1


def test_cli_tui_refuses_outside_a_work(tmp_path):
    """Black-box: `littera tui` outside a work says so and exits non-zero."""
    repo_root = Path(__file__).parents[2]
    result = subprocess.run(
        [f"{repo_root}/.venv/bin/python", "-m", "littera", "tui"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ},
    )
    assert result.returncode != 0
    assert "Not a Littera work" in (result.stderr + result.stdout)


# =============================================================================
# littera-nru — the recovery dialog must not auto-focus "Re-initialize"
# =============================================================================

def test_recovery_dialog_does_not_auto_focus_reinit(pilot_app):
    """Enter on the recovery dialog must never be the button that wipes data."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            app.push_screen(RecoveryDialog("log tail line\n" * 40, can_recover=False))
            await settle(pilot)

            focused = app.screen.focused
            assert focused is not None, "nothing focused: Enter would do nothing"
            assert focused.id == "exit", f"destructive default: focus was {focused.id!r}"

            app.pop_screen()
            await settle(pilot)

    asyncio.run(body())


def test_recovery_dialog_keeps_buttons_reachable_with_a_long_log(pilot_app):
    """A long PG log tail scrolls; it must not push the buttons off-screen."""

    async def body():
        async with pilot_app.run_test() as pilot:
            app = pilot.app
            await settle(pilot)

            app.push_screen(RecoveryDialog("log tail line\n" * 200, can_recover=True))
            await settle(pilot)

            ids = {b.id for b in app.screen.query("Button")}
            assert {"recover", "exit", "reinit"} <= ids

            log = app.screen.query_one("#recovery-log")
            assert log.allow_vertical_scroll, "the log tail is not scrollable"
            assert log.max_scroll_y > 0, "a 200-line log tail does not scroll"
            assert log.region.height <= 14, "log tail is not bounded"
            for button_id in ("recover", "exit", "reinit"):
                button = app.screen.query_one(f"#{button_id}")
                assert button.region.height > 0, f"{button_id} is off-screen"

            app.pop_screen()
            await settle(pilot)

    asyncio.run(body())
