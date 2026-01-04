"""Work database helper.

Goal: make embedded Postgres feel truly embedded.

- Starts Postgres automatically when needed.
- Stops Postgres when the *application* exits, but only if Littera started it.

This module is intentionally small and explicit. It is used by both CLI and TUI.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import json
import os
import sys
import time
import subprocess

import psycopg
import yaml

from littera.db.bootstrap import PostgresConfig, start_postgres, stop_postgres
from littera.db.embedded_pg import EmbeddedPostgresManager


@dataclass(frozen=True)
class WorkDb:
    work_dir: Path
    littera_dir: Path
    cfg: dict
    pg_cfg: PostgresConfig
    conn: psycopg.Connection
    started_here: bool


def load_work_cfg(work_dir: Path | None = None) -> tuple[Path, Path, dict]:
    work_dir = (work_dir or Path.cwd()).resolve()
    littera_dir = work_dir / ".littera"
    if not littera_dir.exists():
        raise RuntimeError("Not a Littera work (missing .littera/)")

    cfg_path = littera_dir / "config.yml"
    if not cfg_path.exists():
        raise RuntimeError("Invalid Littera work (missing config.yml)")

    cfg = yaml.safe_load(cfg_path.read_text())
    return work_dir, littera_dir, cfg


def postgres_config_from_work(littera_dir: Path, cfg: dict) -> PostgresConfig:
    manager = EmbeddedPostgresManager(littera_dir)
    manager.ensure()

    pg = cfg["postgres"]
    return PostgresConfig(
        data_dir=Path(pg["data_dir"]),
        port=pg["port"],
        db_name=pg["db_name"],
        initdb_path=str(manager.initdb_path()),
        pg_ctl_path=str(manager.pg_ctl_path()),
    )


def _lease_path(littera_dir: Path) -> Path:
    return littera_dir / "pg_lease.json"


def pg_lease_seconds() -> int:
    """How long Postgres should remain up after a command.

    This is the "feels embedded" optimization: it avoids repeated startup costs
    across short CLI bursts.

    In test runs, default to 0 to avoid spawning background helpers.
    """

    if "PYTEST_CURRENT_TEST" in os.environ:
        default = 0
    else:
        default = 30

    raw = os.environ.get("LITTERA_PG_LEASE_SECONDS")
    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


def renew_pg_lease(littera_dir: Path, seconds: int) -> None:
    if seconds <= 0:
        return

    lease = {
        "version": 1,
        "expires_at": time.time() + seconds,
    }
    _lease_path(littera_dir).write_text(json.dumps(lease))


def _spawn_lease_watcher(littera_dir: Path) -> None:
    """Spawn a detached process that stops Postgres after lease expiry."""

    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "littera.db.pg_lease",
                "--littera-dir",
                str(littera_dir),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        # If the watcher can't be spawned, we silently fall back to leaving
        # Postgres running. This preserves correctness.
        return


@contextmanager
def open_work_db(work_dir: Path | None = None) -> Iterator[WorkDb]:
    work_dir, littera_dir, cfg = load_work_cfg(work_dir)
    pg_cfg = postgres_config_from_work(littera_dir, cfg)

    started_here = start_postgres(pg_cfg)

    lease_seconds = pg_lease_seconds()
    renew_pg_lease(littera_dir, lease_seconds)
    if started_here and lease_seconds > 0:
        _spawn_lease_watcher(littera_dir)

    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)
    try:
        yield WorkDb(
            work_dir=work_dir,
            littera_dir=littera_dir,
            cfg=cfg,
            pg_cfg=pg_cfg,
            conn=conn,
            started_here=started_here,
        )
    finally:
        conn.close()
        if started_here and lease_seconds <= 0:
            stop_postgres(pg_cfg)
