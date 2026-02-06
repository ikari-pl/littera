"""
Embedded Postgres bootstrap for Littera.

This module defines *mechanics*, not policy.
All concrete decisions (ports, database names, binaries)
come from configuration passed in by the CLI layer.
"""

from pathlib import Path
from dataclasses import dataclass
import shutil
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


class WalCorruptionError(BootstrapError):
    """WAL is corrupted and PG cannot start."""

    def __init__(self, log_tail: str):
        self.log_tail = log_tail
        super().__init__(
            "Database was not shut down cleanly and cannot start. "
            "WAL recovery may be needed."
        )


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
    try:
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
    except subprocess.CalledProcessError:
        log_tail = _read_log_tail(log_file)
        if "could not locate a valid checkpoint record" in log_tail:
            raise WalCorruptionError(log_tail)
        raise
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


def _read_log_tail(log_file: Path, lines: int = 20) -> str:
    """Read the last N lines of a log file, returning '' if missing."""
    if not log_file.exists():
        return ""
    try:
        all_lines = log_file.read_text().splitlines()
        return "\n".join(all_lines[-lines:])
    except OSError:
        return ""


def find_pg_resetwal(cfg: PostgresConfig) -> str | None:
    """Locate the pg_resetwal binary. Returns path or None."""
    # Same directory as pg_ctl (embedded install)
    sibling = Path(cfg.pg_ctl_path).parent / "pg_resetwal"
    if sibling.exists():
        return str(sibling)

    # System PATH
    found = shutil.which("pg_resetwal")
    if found:
        return found

    # Homebrew fallback (macOS)
    for pg_ver in ("18", "17", "16"):
        brew = Path(f"/opt/homebrew/opt/postgresql@{pg_ver}/bin/pg_resetwal")
        if brew.exists():
            return str(brew)

    return None


def reset_wal(cfg: PostgresConfig) -> None:
    """Run pg_resetwal -f on the data directory."""
    binary = find_pg_resetwal(cfg)
    if binary is None:
        raise BootstrapError("pg_resetwal not found — cannot recover WAL")
    subprocess.run(
        [binary, "-f", "-D", str(cfg.data_dir)],
        check=True,
    )


def reinit_cluster(cfg: PostgresConfig) -> None:
    """Delete pgdata and re-initialize the cluster from scratch."""
    if cfg.data_dir.exists():
        shutil.rmtree(cfg.data_dir)
    init_db_cluster(cfg)


def ensure_database(cfg: PostgresConfig) -> None:
    """Ensure the application database exists (idempotent)."""
    import psycopg
    from psycopg import sql

    admin_conn = psycopg.connect(dbname=cfg.admin_db, port=cfg.port)
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (cfg.db_name,),
            )
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(cfg.db_name)
                    )
                )
    finally:
        admin_conn.close()


def bootstrap(cfg: PostgresConfig) -> None:
    """
    Ensure a Postgres cluster exists and is running.

    Schema application and connection management
    are handled by higher layers.
    """
    ensure_data_dir(cfg.data_dir)
    init_db_cluster(cfg)
    start_postgres(cfg)
