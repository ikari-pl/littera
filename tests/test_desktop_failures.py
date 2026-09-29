"""Black-box tests: one failed desktop request must not break the next one.

The sidecar serves every request on one long-lived connection. psycopg leaves
that connection in InFailedSqlTransaction after any error, so without a
rollback a single bad request makes every later request fail until restart.

Hits the real HTTP handlers against embedded Postgres. No mocks.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_desktop_put import sidecar
from test_invariants import add_block, add_document, add_section, init_work

from littera.db.workdb import open_work_db


def call(base: str, method: str, path: str, body: bytes | None = None):
    """Return (status, parsed JSON) without raising on HTTP errors."""
    req = Request(
        f"{base}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def assert_still_serving(base: str) -> None:
    status, docs = call(base, "GET", "/api/documents")
    assert status == 200, docs
    assert isinstance(docs, list), f"connection left unusable: {docs}"
    assert [d["title"] for d in docs] == ["Doc"]


def test_malformed_id_does_not_poison_connection(tmp_path):
    """A Postgres error answers with an error and later requests still work."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")

        with open_work_db(workdir) as db, sidecar(db) as base:
            status, result = call(base, "DELETE", "/api/reviews/not-a-uuid")
            assert status == 200
            assert "error" in result

            assert_still_serving(base)


def test_guard_violation_is_answered_not_dropped(tmp_path):
    """A refused write returns the guard's message instead of a dropped socket."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir)
        add_block(workdir, "One", lang="en")
        add_block(workdir, "Two", lang="en")

        with open_work_db(workdir) as db:
            with db.conn.cursor() as cur:
                cur.execute("SELECT id FROM blocks ORDER BY order_index")
                source_id, target_id = (str(r[0]) for r in cur.fetchall())
            db.conn.commit()

            with sidecar(db) as base:
                payload = {"source_block_id": source_id, "target_block_id": target_id}
                status, result = call(
                    base, "POST", "/api/alignments", json.dumps(payload).encode()
                )
                assert status == 200
                assert "language" in result.get("error", ""), result

                assert_still_serving(base)

            with db.conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM block_alignments")
                assert cur.fetchone()[0] == 0


def test_unexpected_failure_is_a_500_and_server_survives(tmp_path):
    """A malformed body is not a domain refusal: 500, then keep serving."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")

        with open_work_db(workdir) as db, sidecar(db) as base:
            status, result = call(base, "POST", "/api/documents", b"{not json")
            assert status == 500
            assert "error" in result

            assert_still_serving(base)
