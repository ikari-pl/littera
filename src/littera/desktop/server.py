"""Littera desktop sidecar — lightweight HTTP API for the WebView frontend.

Starts embedded Postgres via the existing open_work_db() lifecycle,
then serves a minimal JSON API until stdin closes (signaling the
Tauri shell has exited).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from littera.db.workdb import open_work_db, WorkDb


# =============================================================================
# Route table — (pattern, method, handler_name)
# =============================================================================

ROUTES = [
    (re.compile(r"^/api/documents$"), "GET", "_get_documents"),
    (re.compile(r"^/api/documents/([^/]+)/sections$"), "GET", "_get_sections"),
    (re.compile(r"^/api/sections/([^/]+)/blocks$"), "GET", "_get_blocks"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "GET", "_get_block"),
    (re.compile(r"^/api/entities$"), "GET", "_get_entities"),
    (re.compile(r"^/api/entities/([^/]+)$"), "GET", "_get_entity"),
    (re.compile(r"^/api/status$"), "GET", "_get_status"),
    (re.compile(r"^/health$"), "GET", "_health"),
]


class SidecarHandler(BaseHTTPRequestHandler):
    """Thin HTTP handler — delegates all DB access to the shared WorkDb."""

    work_db: WorkDb  # Set by serve()

    def do_GET(self):
        for pattern, method, handler_name in ROUTES:
            m = pattern.match(self.path)
            if m and method == "GET":
                handler = getattr(self, handler_name)
                self._json_response(handler(*m.groups()))
                return
        self.send_error(404)

    # -----------------------------------------------------------------
    # Route handlers
    # -----------------------------------------------------------------

    def _get_documents(self):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM documents ORDER BY order_index, created_at"
            )
            return [{"id": str(r[0]), "title": r[1]} for r in cur.fetchall()]

    def _get_sections(self, document_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                (document_id,),
            )
            return [{"id": str(r[0]), "title": r[1]} for r in cur.fetchall()]

    def _get_blocks(self, section_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                (section_id,),
            )
            return [
                {"id": str(r[0]), "language": r[1], "source_text": r[2]}
                for r in cur.fetchall()
            ]

    def _get_block(self, block_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, language, source_text FROM blocks WHERE id = %s",
                (block_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            return {"id": str(row[0]), "language": row[1], "source_text": row[2]}

    def _get_entities(self):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
            )
            return [
                {
                    "id": str(r[0]),
                    "entity_type": r[1],
                    "label": r[2] or "(unnamed)",
                }
                for r in cur.fetchall()
            ]

    def _get_entity(self, entity_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            entity_type, name = row

            # Work-scoped note
            work_id = self.work_db.cfg.get("work", {}).get("id")
            note = None
            if work_id is not None:
                cur.execute(
                    """
                    SELECT metadata->>'note'
                    FROM entity_work_metadata
                    WHERE entity_id = %s AND work_id = %s
                    """,
                    (entity_id, work_id),
                )
                note_row = cur.fetchone()
                note = note_row[0] if note_row else None

            # Labels
            cur.execute(
                """
                SELECT language, base_form, aliases
                FROM entity_labels
                WHERE entity_id = %s
                ORDER BY language
                """,
                (entity_id,),
            )
            labels = [
                {"language": r[0], "base_form": r[1], "aliases": r[2]}
                for r in cur.fetchall()
            ]

            # Mentions
            cur.execute(
                """
                SELECT d.title, s.title, b.language, b.source_text
                FROM mentions m
                JOIN blocks b ON b.id = m.block_id
                JOIN sections s ON s.id = b.section_id
                JOIN documents d ON d.id = s.document_id
                WHERE m.entity_id = %s
                ORDER BY b.created_at DESC
                LIMIT 10
                """,
                (entity_id,),
            )
            mentions = [
                {
                    "document": r[0],
                    "section": r[1],
                    "language": r[2],
                    "preview": r[3].replace("\n", " ")[:80],
                }
                for r in cur.fetchall()
            ]

            return {
                "entity_type": entity_type,
                "label": name or "(unnamed)",
                "labels": labels,
                "mentions": mentions,
                "note": note,
            }

    def _get_status(self):
        cfg = self.work_db.cfg
        work_title = cfg.get("work", {}).get("title", "Untitled")
        return {"work_title": work_title, "pg_status": "running"}

    def _health(self):
        return {"status": "ok"}

    # -----------------------------------------------------------------
    # Response helpers
    # -----------------------------------------------------------------

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress per-request logs


def _wait_for_stdin_close():
    """Block until stdin is closed (Tauri process exited)."""
    try:
        while True:
            # select() on stdin — returns when readable (EOF) or error
            readable, _, _ = select.select([sys.stdin], [], [])
            if readable:
                data = sys.stdin.buffer.read(1)
                if not data:  # EOF
                    break
    except (OSError, ValueError):
        pass


def serve(wdb: WorkDb, port: int = 0):
    """Start the HTTP server, print readiness signal, block until stdin closes."""

    SidecarHandler.work_db = wdb
    server = HTTPServer(("127.0.0.1", port), SidecarHandler)
    actual_port = server.server_address[1]

    # Start serving in a background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Signal readiness to Tauri (stdout line protocol)
    print(f"LITTERA_SIDECAR_READY:{actual_port}", flush=True)

    # Block until stdin closes (Tauri exited)
    _wait_for_stdin_close()

    server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Littera desktop sidecar")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Path to Littera work directory (default: cwd)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind (default: OS-assigned)",
    )
    args = parser.parse_args()

    # The sidecar owns Postgres for its full lifetime — disable the lease
    # watcher so PG isn't killed after 30s. PG stops when this process exits.
    os.environ["LITTERA_PG_LEASE_SECONDS"] = "0"

    with open_work_db(args.work_dir) as wdb:
        serve(wdb, port=args.port)


if __name__ == "__main__":
    main()
