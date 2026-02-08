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
    (re.compile(r"^/api/documents$"), "POST", "_post_document"),
    (re.compile(r"^/api/documents/([^/]+)$"), "PUT", "_put_document"),
    (re.compile(r"^/api/documents/([^/]+)$"), "DELETE", "_delete_document"),
    (re.compile(r"^/api/documents/([^/]+)/sections$"), "GET", "_get_sections"),
    (re.compile(r"^/api/sections$"), "POST", "_post_section"),
    (re.compile(r"^/api/sections/([^/]+)$"), "PUT", "_put_section"),
    (re.compile(r"^/api/sections/([^/]+)$"), "DELETE", "_delete_section"),
    (re.compile(r"^/api/sections/([^/]+)/blocks$"), "GET", "_get_blocks"),
    (re.compile(r"^/api/blocks/batch$"), "PUT", "_put_blocks_batch"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "GET", "_get_block"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "PUT", "_put_block"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "DELETE", "_delete_block"),
    (re.compile(r"^/api/blocks$"), "POST", "_post_block"),
    (re.compile(r"^/api/entities$"), "GET", "_get_entities"),
    (re.compile(r"^/api/entities$"), "POST", "_post_entity"),
    (re.compile(r"^/api/entities/([^/]+)$"), "GET", "_get_entity"),
    (re.compile(r"^/api/entities/([^/]+)$"), "DELETE", "_delete_entity"),
    (re.compile(r"^/api/entities/([^/]+)/note$"), "PUT", "_put_entity_note"),
    (re.compile(r"^/api/entities/([^/]+)/labels$"), "POST", "_post_entity_label"),
    (re.compile(r"^/api/labels/([^/]+)$"), "DELETE", "_delete_label"),
    (re.compile(r"^/api/mentions/([^/]+)$"), "DELETE", "_delete_mention"),
    (re.compile(r"^/api/status$"), "GET", "_get_status"),
    (re.compile(r"^/health$"), "GET", "_health"),
]


class SidecarHandler(BaseHTTPRequestHandler):
    """Thin HTTP handler — delegates all DB access to the shared WorkDb."""

    work_db: WorkDb  # Set by serve()

    def do_GET(self):
        self._dispatch("GET")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _dispatch(self, method):
        for pattern, route_method, handler_name in ROUTES:
            m = pattern.match(self.path)
            if m and route_method == method:
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
                "SELECT id, block_type, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                (section_id,),
            )
            return [
                {"id": str(r[0]), "block_type": r[1], "language": r[2], "source_text": r[3]}
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
                SELECT id, language, base_form, aliases
                FROM entity_labels
                WHERE entity_id = %s
                ORDER BY language
                """,
                (entity_id,),
            )
            labels = [
                {"id": str(r[0]), "language": r[1], "base_form": r[2], "aliases": r[3]}
                for r in cur.fetchall()
            ]

            # Mentions
            cur.execute(
                """
                SELECT m.id, m.block_id, d.title, s.title, b.language, b.source_text
                FROM mentions m
                JOIN blocks b ON b.id = m.block_id
                JOIN sections s ON s.id = b.section_id
                JOIN documents d ON d.id = s.document_id
                WHERE m.entity_id = %s
                ORDER BY b.created_at DESC
                """,
                (entity_id,),
            )
            mentions = [
                {
                    "id": str(r[0]),
                    "block_id": str(r[1]),
                    "document": r[2],
                    "section": r[3],
                    "language": r[4],
                    "preview": r[5].replace("\n", " ")[:80],
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
    # Write handlers
    # -----------------------------------------------------------------

    def _put_document(self, document_id: str):
        body = self._read_json_body()
        title = body.get("title")
        if title is None:
            return {"error": "title required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET title = %s WHERE id = %s",
                (title, document_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_section(self, section_id: str):
        body = self._read_json_body()
        title = body.get("title")
        if title is None:
            return {"error": "title required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sections SET title = %s WHERE id = %s",
                (title, section_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_block(self, block_id: str):
        body = self._read_json_body()
        source_text = body.get("source_text")
        if source_text is None:
            return {"error": "source_text required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE blocks SET source_text = %s WHERE id = %s",
                (source_text, block_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_blocks_batch(self):
        body = self._read_json_body()
        blocks = body.get("blocks", [])
        conn = self.work_db.conn
        with conn.cursor() as cur:
            for b in blocks:
                cur.execute(
                    "UPDATE blocks SET source_text = %s WHERE id = %s",
                    (b["source_text"], b["id"]),
                )
        conn.commit()
        return {"ok": True, "count": len(blocks)}

    def _post_block(self):
        body = self._read_json_body()
        block_id = body.get("id")
        section_id = body.get("section_id")
        block_type = body.get("block_type", "prose")
        language = body.get("language", "en")
        source_text = body.get("source_text", "")
        if not section_id:
            return {"error": "section_id required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            if block_id:
                cur.execute(
                    "INSERT INTO blocks (id, section_id, block_type, language, source_text) VALUES (%s, %s, %s, %s, %s)",
                    (block_id, section_id, block_type, language, source_text),
                )
            else:
                cur.execute(
                    "INSERT INTO blocks (section_id, block_type, language, source_text) VALUES (%s, %s, %s, %s) RETURNING id",
                    (section_id, block_type, language, source_text),
                )
                block_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": str(block_id)}

    def _delete_block(self, block_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM blocks WHERE id = %s", (block_id,))
        conn.commit()
        return {"ok": True}

    def _post_document(self):
        body = self._read_json_body()
        title = body.get("title", "Untitled")
        work_id = self.work_db.cfg.get("work", {}).get("id")
        if work_id is None:
            return {"error": "no work_id in config"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (work_id, title) VALUES (%s, %s) RETURNING id",
                (work_id, title),
            )
            doc_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": doc_id}

    def _delete_document(self, document_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        conn.commit()
        return {"ok": True}

    def _post_section(self):
        body = self._read_json_body()
        document_id = body.get("document_id")
        title = body.get("title", "Untitled")
        if not document_id:
            return {"error": "document_id required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sections (document_id, title, order_index) "
                "VALUES (%s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1)) "
                "RETURNING id",
                (document_id, title, document_id),
            )
            section_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": section_id}

    def _delete_section(self, section_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sections WHERE id = %s", (section_id,))
        conn.commit()
        return {"ok": True}

    def _post_entity(self):
        body = self._read_json_body()
        entity_type = body.get("entity_type", "concept")
        label = body.get("label", "")
        if not label:
            return {"error": "label required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO entities (entity_type, canonical_label) VALUES (%s, %s) RETURNING id",
                (entity_type, label),
            )
            entity_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": entity_id}

    def _delete_entity(self, entity_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
        conn.commit()
        return {"ok": True}

    def _delete_mention(self, mention_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mentions WHERE id = %s", (mention_id,))
        conn.commit()
        return {"ok": True}

    def _put_entity_note(self, entity_id: str):
        body = self._read_json_body()
        note = body.get("note", "")
        work_id = self.work_db.cfg.get("work", {}).get("id")
        if work_id is None:
            return {"error": "no work_id in config"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (entity_id, work_id)
                DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                (entity_id, work_id, json.dumps({"note": note})),
            )
        conn.commit()
        return {"ok": True}

    def _post_entity_label(self, entity_id: str):
        body = self._read_json_body()
        language = body.get("language", "en")
        base_form = body.get("base_form", "")
        aliases = body.get("aliases")
        if not base_form:
            return {"error": "base_form required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO entity_labels (entity_id, language, base_form, aliases) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (entity_id, language, base_form, json.dumps(aliases) if aliases else None),
            )
            label_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": label_id}

    def _delete_label(self, label_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entity_labels WHERE id = %s", (label_id,))
        conn.commit()
        return {"ok": True}

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

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
