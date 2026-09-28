"""Black-box tests for desktop sidecar PUT review and block-order handlers.

Hits the real HTTP handlers against embedded Postgres. No mocks.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from http.server import HTTPServer
from threading import Thread
from urllib.request import Request, urlopen

from littera.db.workdb import open_work_db
from littera.desktop.server import SidecarHandler
from test_invariants import add_block, add_document, add_section, init_work, run


@contextmanager
def sidecar(wdb):
    """Serve SidecarHandler on an ephemeral localhost port."""
    SidecarHandler.work_db = wdb
    server = HTTPServer(("127.0.0.1", 0), SidecarHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def put_json(base: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = Request(
        f"{base}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def test_put_review_updates_description_and_severity(tmp_path):
    """PUT review updates description/severity and persists in DB."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Original text' --severity=low", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT id FROM reviews")
            review_id = str(cur.fetchone()[0])

            with sidecar(db) as base:
                result = put_json(
                    base,
                    f"/api/reviews/{review_id}",
                    {"description": "Revised text", "severity": "high"},
                )
            assert result.get("ok") is True, result

            cur.execute(
                "SELECT description, severity FROM reviews WHERE id = %s",
                (review_id,),
            )
            desc, severity = cur.fetchone()
            assert desc == "Revised text"
            assert severity == "high"

        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Revised text" in res.stdout
        assert "[high]" in res.stdout
        assert "Original text" not in res.stdout


def test_put_review_scope_without_scope_id_rejected(tmp_path):
    """PUT review with scope but no scope_id is rejected."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Global note'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT id, scope, scope_id FROM reviews")
            review_id, scope_before, scope_id_before = cur.fetchone()
            review_id = str(review_id)

            with sidecar(db) as base:
                result = put_json(
                    base,
                    f"/api/reviews/{review_id}",
                    {"scope": "block"},
                )
            assert "error" in result
            assert "scope_id" in result["error"]

            cur.execute(
                "SELECT scope, scope_id, description FROM reviews WHERE id = %s",
                (review_id,),
            )
            scope, scope_id, description = cur.fetchone()
            assert scope == scope_before
            assert scope_id == scope_id_before
            assert description == "Global note"


def test_put_review_invalid_scope_rejected(tmp_path):
    """PUT review with invalid scope is rejected."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Keep scope'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT id, scope FROM reviews")
            review_id, scope_before = cur.fetchone()
            review_id = str(review_id)

            with sidecar(db) as base:
                result = put_json(
                    base,
                    f"/api/reviews/{review_id}",
                    {"scope": "paragraph", "scope_id": review_id},
                )
            assert "error" in result
            assert "invalid scope" in result["error"]

            cur.execute("SELECT scope, description FROM reviews WHERE id = %s", (review_id,))
            scope, description = cur.fetchone()
            assert scope == scope_before
            assert description == "Keep scope"


def test_put_block_order_moves_block(tmp_path):
    """PUT block order moves a block; CLI list and DB order_index match."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")
        add_block(workdir, "Third")

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT id, source_text FROM blocks "
                "ORDER BY order_index NULLS LAST, created_at, id"
            )
            rows = cur.fetchall()
            assert [r[1] for r in rows] == ["First", "Second", "Third"]
            third_id = str(rows[2][0])

            with sidecar(db) as base:
                result = put_json(
                    base,
                    f"/api/blocks/{third_id}/order",
                    {"position": 1},
                )
            assert result.get("ok") is True, result

            cur.execute(
                "SELECT source_text, order_index FROM blocks ORDER BY order_index, id"
            )
            ordered = cur.fetchall()
            assert [r[0] for r in ordered] == ["Third", "First", "Second"]
            assert [r[1] for r in ordered] == [1, 2, 3]

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) Third" in res.stdout
        assert "[2] (en) First" in res.stdout
        assert "[3] (en) Second" in res.stdout


def test_put_block_order_out_of_range_rejected(tmp_path):
    """PUT block order with out-of-range position is rejected."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "Only")
        add_block(workdir, "Also")

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT id, source_text, order_index FROM blocks "
                "ORDER BY order_index NULLS LAST, created_at, id"
            )
            before = cur.fetchall()
            first_id = str(before[0][0])

            with sidecar(db) as base:
                result = put_json(
                    base,
                    f"/api/blocks/{first_id}/order",
                    {"position": 5},
                )
            assert "error" in result
            assert "position must be between" in result["error"]

            cur.execute(
                "SELECT id, source_text, order_index FROM blocks "
                "ORDER BY order_index NULLS LAST, created_at, id"
            )
            after = cur.fetchall()
            assert after == before

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) Only" in res.stdout
        assert "[2] (en) Also" in res.stdout


def get_json(base: str, path: str) -> dict:
    with urlopen(f"{base}{path}") as resp:
        return json.loads(resp.read().decode())


def test_status_and_wc_count_saved_words(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Ch")
        add_section(workdir)
        add_block(workdir, "one two three")

        with open_work_db(workdir) as db:
            with sidecar(db) as base:
                status = get_json(base, "/api/status")
                assert status["word_count"] == 3
                assert status["words"] == 3
                assert status["blocks"] == 1
                wc = get_json(base, "/api/wc")
                assert wc["words"] == 3
                assert wc["blocks"] == 1


def test_export_markdown_compile_query(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Ch")
        add_section(workdir, "S")
        add_block(workdir, "Hello world")

        with open_work_db(workdir) as db:
            with sidecar(db) as base:
                labeled = get_json(base, "/api/export/markdown")
                compiled = get_json(base, "/api/export/markdown?compile=1")
        assert "## Document: Ch" in labeled["markdown"]
        assert "[en] Hello world" in labeled["markdown"]
        assert "## Document:" not in compiled["markdown"]
        assert "[en]" not in compiled["markdown"]
        assert "## Ch" in compiled["markdown"]
        assert "Hello world" in compiled["markdown"]
