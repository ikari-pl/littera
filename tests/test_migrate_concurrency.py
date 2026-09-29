"""migrate() must be safe when two interfaces open the same work at once.

Every CLI command, the TUI and the desktop sidecar run migrate() on open.
Launched together with a migration pending, both used to read the same
current version and both apply it. Harmless for an IF NOT EXISTS migration,
data corruption for anything else.

Real embedded Postgres, two real connections. No mocks.
"""

from __future__ import annotations

import threading

import psycopg
import pytest
from test_invariants import init_work

import littera.db.migrate as migrate_mod
from littera.db.migrate import migrate
from littera.db.workdb import open_work_db


def _second_connection(conn) -> psycopg.Connection:
    info = conn.info
    return psycopg.connect(dbname=info.dbname, port=info.port, host=info.host)


def _count(conn, sql: str, params=()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def test_concurrent_migrate_applies_each_migration_once(tmp_path, monkeypatch):
    with init_work(tmp_path) as workdir, open_work_db(workdir) as db:
        current = _count(db.conn, "SELECT MAX(version) FROM schema_version")
        db.conn.execute("CREATE TABLE migration_probe (id serial PRIMARY KEY)")
        db.conn.commit()

        # A migration that is NOT idempotent, slow enough that both callers
        # are inside migrate() at the same time.
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / f"{current + 1:04d}_probe.sql").write_text(
            "SELECT pg_sleep(0.5);\nINSERT INTO migration_probe DEFAULT VALUES;\n"
        )
        monkeypatch.setattr(migrate_mod, "MIGRATIONS_DIR", migrations)

        other = _second_connection(db.conn)
        start = threading.Barrier(2)
        errors: list[BaseException] = []

        def run(conn):
            start.wait()
            try:
                migrate(conn)
            except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(c,)) for c in (db.conn, other)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        other.close()

        assert not errors, errors
        assert _count(db.conn, "SELECT count(*) FROM migration_probe") == 1
        assert (
            _count(
                db.conn,
                "SELECT count(*) FROM schema_version WHERE version = %s",
                (current + 1,),
            )
            == 1
        )


def test_schema_version_rejects_duplicates_after_migrate(tmp_path):
    """A work double-applied by an older Littera heals, then stays unique."""
    with init_work(tmp_path) as workdir, open_work_db(workdir) as db:
        current = _count(db.conn, "SELECT MAX(version) FROM schema_version")
        # open_work_db() already migrated; recreate a work from before the
        # unique index, carrying the duplicate a past race left behind.
        db.conn.execute("DROP INDEX IF EXISTS schema_version_version_key")
        db.conn.execute(
            "INSERT INTO schema_version (version) VALUES (%s)", (current,)
        )
        db.conn.commit()

        migrate(db.conn)

        assert (
            _count(
                db.conn,
                "SELECT count(*) FROM schema_version WHERE version = %s",
                (current,),
            )
            == 1
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.conn.execute(
                "INSERT INTO schema_version (version) VALUES (%s)", (current,)
            )
        db.conn.rollback()
