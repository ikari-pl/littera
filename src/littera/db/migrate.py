"""Schema migration engine for Littera.

Applies numbered SQL migration files in order, tracking progress
in a schema_version table. Forward-only, idempotent on re-run.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "db" / "migrations"

# Postgres advisory lock key serialising migrate() across processes. The CLI,
# TUI and desktop sidecar all migrate on open; any fixed number works as long
# as every caller uses the same one. ("LITTERA" in ASCII.)
MIGRATE_LOCK_KEY = 0x4C4954544552_41


def _ensure_version_table(conn) -> None:
    """Create schema_version table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    # Works opened by two interfaces at once, before migrate() took a lock,
    # may record a version twice. Keep the earliest row per version, then let
    # Postgres refuse duplicates from here on.
    conn.execute("""
        DELETE FROM schema_version a
        USING schema_version b
        WHERE a.version = b.version
          AND (a.applied_at, a.ctid) > (b.applied_at, b.ctid)
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS schema_version_version_key "
        "ON schema_version (version)"
    )
    conn.commit()


def _current_version(conn) -> int:
    """Return the highest applied migration version, or 0."""
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    return cur.fetchone()[0]


def _migration_files() -> list[tuple[int, Path]]:
    """Return sorted list of (version, path) for all migration files."""
    if not MIGRATIONS_DIR.exists():
        return []
    files = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Expected format: 0001_description.sql
        try:
            version = int(p.stem.split("_", 1)[0])
        except (ValueError, IndexError):
            continue
        files.append((version, p))
    return files


def migrate(conn) -> int:
    """Apply all pending migrations. Returns number of migrations applied.

    Holds a session advisory lock for the whole run, so a second process
    migrating the same work waits, then reads the version the first one
    reached instead of applying the same migrations again.
    """
    conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATE_LOCK_KEY,))
    conn.commit()
    try:
        _ensure_version_table(conn)
        current = _current_version(conn)
        applied = 0

        for version, path in _migration_files():
            if version <= current:
                continue
            sql = path.read_text()
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (%s)",
                (version,),
            )
            conn.commit()
            applied += 1

        return applied
    except BaseException:
        conn.rollback()
        raise
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATE_LOCK_KEY,))
            conn.commit()
        except psycopg.Error:
            # A session lock dies with its connection; if the connection is
            # gone there is nothing left to release.
            pass
