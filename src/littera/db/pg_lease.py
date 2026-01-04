"""Background helper to stop embedded Postgres after lease expiry."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from littera.db.bootstrap import stop_postgres
from littera.db.workdb import load_work_cfg, postgres_config_from_work


def _lease_path(littera_dir: Path) -> Path:
    return littera_dir / "pg_lease.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--littera-dir", required=True)
    args = parser.parse_args(argv)

    littera_dir = Path(args.littera_dir).resolve()
    work_dir = littera_dir.parent

    try:
        _, _, cfg = load_work_cfg(work_dir)
    except Exception:
        return 0

    pg_cfg = postgres_config_from_work(littera_dir, cfg)

    lease_path = _lease_path(littera_dir)

    while True:
        if not lease_path.exists():
            return 0

        try:
            lease = json.loads(lease_path.read_text())
            expires_at = float(lease.get("expires_at", 0))
        except Exception:
            return 0

        now = time.time()
        if expires_at <= now:
            stop_postgres(pg_cfg)
            return 0

        # Sleep until expiry (cap to allow rapid renewal).
        sleep_for = min(expires_at - now, 5.0)
        time.sleep(max(sleep_for, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
