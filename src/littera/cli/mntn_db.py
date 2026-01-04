"""Maintenance commands for the embedded database.

These are intentionally explicit and slightly verbose.

Prefix: mntn-db-*
"""

from __future__ import annotations

import json
import sys
import time

import typer

from littera.db.bootstrap import start_postgres, stop_postgres
from littera.db.workdb import (
    load_work_cfg,
    postgres_config_from_work,
    pg_lease_seconds,
    renew_pg_lease,
    _spawn_lease_watcher,
)


def register(app: typer.Typer) -> None:
    app.command("mntn-db-status")(mntn_db_status)
    app.command("mntn-db-start")(mntn_db_start)
    app.command("mntn-db-stop")(mntn_db_stop)
    app.command("mntn-db-lease")(mntn_db_lease)


def mntn_db_status() -> None:
    """Show embedded DB status for this work."""

    try:
        work_dir, littera_dir, cfg = load_work_cfg()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    pg_cfg = postgres_config_from_work(littera_dir, cfg)

    pid_file = pg_cfg.data_dir / "postmaster.pid"
    if pid_file.exists():
        print(f"Postgres: running (port {pg_cfg.port})")
    else:
        print("Postgres: not running")

    lease_path = littera_dir / "pg_lease.json"
    if lease_path.exists():
        try:
            lease = json.loads(lease_path.read_text())
            expires_at = float(lease.get("expires_at", 0))
            seconds_left = int(expires_at - time.time())
            print(f"Lease: expires in {max(seconds_left, 0)}s")
        except Exception:
            print("Lease: unreadable")
    else:
        print("Lease: none")


def mntn_db_start(
    lease_seconds: int = typer.Option(
        None,
        help="Override lease duration (seconds). 0 disables lease.",
    ),
) -> None:
    """Start embedded Postgres for this work."""

    try:
        _, littera_dir, cfg = load_work_cfg()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    pg_cfg = postgres_config_from_work(littera_dir, cfg)

    started_here = start_postgres(pg_cfg)

    seconds = pg_lease_seconds() if lease_seconds is None else lease_seconds
    renew_pg_lease(littera_dir, seconds)
    if started_here and seconds > 0:
        _spawn_lease_watcher(littera_dir)

    if started_here:
        print(f"✓ Started Postgres (port {pg_cfg.port})")
    else:
        print(f"✓ Postgres already running (port {pg_cfg.port})")


def mntn_db_stop(
    mode: str = typer.Option(
        "fast",
        help="Stop mode: smart | fast | immediate",
    ),
) -> None:
    """Stop embedded Postgres for this work."""

    try:
        _, littera_dir, cfg = load_work_cfg()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    pg_cfg = postgres_config_from_work(littera_dir, cfg)

    stopped = stop_postgres(pg_cfg, mode=mode)
    if stopped:
        print("✓ Stopped Postgres")
    else:
        print("Postgres was not running")


def mntn_db_lease(
    seconds: int = typer.Argument(None, help="New lease duration in seconds"),
) -> None:
    """Show or set the lease timer for this work."""

    try:
        _, littera_dir, _ = load_work_cfg()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    lease_path = littera_dir / "pg_lease.json"

    if seconds is None:
        if not lease_path.exists():
            print("(no lease)")
            return
        try:
            lease = json.loads(lease_path.read_text())
            expires_at = float(lease.get("expires_at", 0))
            seconds_left = int(expires_at - time.time())
            print(max(seconds_left, 0))
            return
        except Exception:
            print("(unreadable)")
            sys.exit(1)

    renew_pg_lease(littera_dir, seconds)
    print(f"✓ Lease renewed: {seconds}s")
