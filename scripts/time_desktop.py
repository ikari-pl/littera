"""Time the desktop sidecar's HTTP API against an existing work (littera-496).

    python scripts/time_desktop.py WORK_DIR [--runs 3]

Serves the real SidecarHandler on a local port and times the requests the
desktop frontend makes, including the whole-work ones.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from littera.db.workdb import open_work_db
from littera.desktop.server import SidecarHandler

PATHS = [
    "/api/status",
    "/api/wc",
    "/api/documents",
    "/api/blocks",  # every block, for the alignment picker
    "/api/entities",
    "/api/entities/{first_entity}",  # detail: labels, note, every mention
    "/api/reviews",
    "/api/alignment-gaps",
    "/api/export/json",
    "/api/export/markdown?compile=1",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    with open_work_db(args.work_dir) as db:
        SidecarHandler.work_db = db
        server = HTTPServer(("127.0.0.1", 0), SidecarHandler)
        Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urlopen(base + "/api/entities") as resp:
                listed = json.loads(resp.read())
            first_entity = listed[0]["id"] if listed else None
            for path in PATHS:
                if "{first_entity}" in path:
                    if first_entity is None:
                        continue
                    path = path.format(first_entity=first_entity)
                samples, size = [], 0
                for _ in range(args.runs):
                    start = time.perf_counter()
                    with urlopen(base + path) as resp:
                        body = resp.read()
                    samples.append(time.perf_counter() - start)
                    size = len(body)
                    if isinstance(json.loads(body), dict) and "error" in json.loads(body):
                        raise SystemExit(f"{path}: {json.loads(body)['error']}")
                print(
                    f"GET {path:34} {statistics.median(samples) * 1000:7.0f} ms"
                    f"  ({size / 1024:,.0f} KiB)"
                )
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
