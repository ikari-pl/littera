"""Littera desktop sidecar — lightweight HTTP API for the WebView frontend.

Starts embedded Postgres via the existing open_work_db() lifecycle,
then serves a minimal JSON API until stdin closes (signaling the
Tauri shell has exited).
"""

from __future__ import annotations

import argparse
import json
import select
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from littera.db.workdb import open_work_db, WorkDb


class SidecarHandler(BaseHTTPRequestHandler):
    """Thin HTTP handler — delegates all DB access to the shared WorkDb."""

    work_db: WorkDb  # Set by serve()

    def do_GET(self):
        if self.path == "/api/documents":
            self._json_response(self._get_documents())
        elif self.path == "/health":
            self._json_response({"status": "ok"})
        else:
            self.send_error(404)

    def _get_documents(self):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM documents ORDER BY order_index, created_at"
            )
            return [{"id": str(r[0]), "title": r[1]} for r in cur.fetchall()]

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

    with open_work_db(args.work_dir) as wdb:
        serve(wdb, port=args.port)


if __name__ == "__main__":
    main()
