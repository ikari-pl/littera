"""Untitled documents and sections must be navigable in the TUI.

The schema allows a NULL title and import creates untitled sections (a scene
break in a manuscript has no heading). The TUI assumed every title was a
string: rows read "None", and Enter on an untitled section crashed the
breadcrumb, leaving an empty screen over a section that still held its text.
Driven with Textual's Pilot against the real app and embedded Postgres.
"""

import asyncio

import psycopg
from textual.widgets import ListView, Static

from tests.tui.conftest import settle

SCENE_TEXT = "The scene under a break keeps all of its words."


def _rows(app) -> list[str]:
    nav = app.screen.query_one("#nav", ListView)
    return [" ".join(str(w.render()) for w in item.query(Static)) for item in nav.children]


def test_untitled_section_is_labelled_and_opens(pilot_app, seeded_work):
    _workdir, _cfg, pg_cfg = seeded_work
    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT d.id FROM documents d ORDER BY d.order_index NULLS LAST, d.created_at LIMIT 1"
        )
        doc_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO sections (document_id, title, order_index) "
            "VALUES (%s, NULL, 0) RETURNING id",
            (doc_id,),
        )
        section_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO blocks (section_id, block_type, language, source_text) "
            "VALUES (%s, 'paragraph', 'en', %s)",
            (section_id, SCENE_TEXT),
        )
    conn.commit()

    async def body():
        async with pilot_app.run_test(size=(120, 30)) as pilot:
            app = pilot.app
            await settle(pilot)
            await pilot.press("enter")  # first document -> its sections
            await settle(pilot)

            rows = _rows(app)
            assert not any("None" in r for r in rows), rows
            assert any("(untitled)" in r for r in rows), rows

            nav = app.screen.query_one("#nav", ListView)
            nav.index = next(i for i, r in enumerate(rows) if "(untitled)" in r)
            await settle(pilot)
            await pilot.press("enter")  # untitled section -> its blocks
            await settle(pilot)

            breadcrumb = str(app.screen.query_one("#breadcrumb", Static).render())
            assert "(untitled)" in breadcrumb
            assert any(SCENE_TEXT[:30] in r for r in _rows(app))

    try:
        asyncio.run(body())
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sections WHERE id = %s", (section_id,))
        conn.commit()
        conn.close()
