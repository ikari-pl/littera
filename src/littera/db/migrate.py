"""Schema migration engine for Littera.

Applies numbered SQL migration files in order, tracking progress
in a schema_version table. Forward-only, idempotent on re-run.
"""

from __future__ import annotations

from pathlib import Path


MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "db" / "migrations"


def _ensure_version_table(conn) -> None:
    """Create schema_version table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
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
    """Apply all pending migrations. Returns number of migrations applied."""
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
