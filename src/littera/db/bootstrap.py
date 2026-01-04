"""
Embedded Postgres bootstrap for Littera.

This module defines *mechanics*, not policy.
All concrete decisions (ports, database names, binaries)
come from configuration passed in by the CLI layer.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import subprocess
import os


@dataclass
class PostgresConfig:
    data_dir: Path
    port: int
    db_name: str
    admin_db: str = "postgres"
    initdb_path: str = "initdb"
    pg_ctl_path: str = "pg_ctl"


class BootstrapError(RuntimeError):
    pass


def ensure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def init_db_cluster(cfg: PostgresConfig) -> None:
    if (cfg.data_dir / "PG_VERSION").exists():
        return

    subprocess.run(
        [
            cfg.initdb_path,
            "-D",
            str(cfg.data_dir),
            "--no-locale",
            "--encoding=UTF8",
        ],
        check=True,
    )


def start_postgres(cfg: PostgresConfig) -> bool:
    """Start Postgres for this cluster.

    Returns True if this call started Postgres, False if it was already running.
    """

    pid_file = cfg.data_dir / "postmaster.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().splitlines()[0])
            os.kill(pid, 0)
            # ✅ Postgres is already running
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            # Stale PID file
            pid_file.unlink()

    log_file = cfg.data_dir / "postgres.log"
    subprocess.run(
        [
            cfg.pg_ctl_path,
            "-D",
            str(cfg.data_dir),
            "-l",
            str(log_file),
            "-o",
            f"-F -p {cfg.port}",
            "-w",
            "start",
        ],
        check=True,
    )
    return True


def stop_postgres(cfg: PostgresConfig, *, mode: str = "fast") -> bool:
    """Stop Postgres for this cluster.

    Returns True if Postgres was running and we asked it to stop.
    """

    pid_file = cfg.data_dir / "postmaster.pid"
    if not pid_file.exists():
        return False

    subprocess.run(
        [
            cfg.pg_ctl_path,
            "-D",
            str(cfg.data_dir),
            "-m",
            mode,
            "-w",
            "stop",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return True


def bootstrap(cfg: PostgresConfig) -> None:
    """
    Ensure a Postgres cluster exists and is running.

    Schema application and connection management
    are handled by higher layers.
    """
    ensure_data_dir(cfg.data_dir)
    init_db_cluster(cfg)
    start_postgres(cfg)
