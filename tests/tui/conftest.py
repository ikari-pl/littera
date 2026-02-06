"""Shared fixtures for TUI tests with real embedded Postgres.

Per MANIFESTO: no mocks for core behavior. Views query a real database.

Note: Views are now pure functions of state (no DB access in render()).
Tests must call queries.refresh_outline() or queries.refresh_entities()
before view.render() to populate state with DB data.
"""

import os
import subprocess
from pathlib import Path

import psycopg
import pytest
import yaml

from littera.db.bootstrap import PostgresConfig, start_postgres, stop_postgres
from littera.db.embedded_pg import EmbeddedPostgresManager
from littera.tui.state import AppState


def _run_cli(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).parents[2]
    python_path = f"{repo_root}/.venv/bin/python"
    if cmd.startswith("littera "):
        cmd = f"{python_path} -m littera {cmd[8:]}"
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": os.environ.get("PATH", "")},
    )


@pytest.fixture(scope="session")
def seeded_work(tmp_path_factory):
    """Session-scoped: init work, seed data, keep PG running for all TUI tests."""
    workdir = tmp_path_factory.mktemp("tui_test")

    res = _run_cli("littera init .", workdir)
    assert res.returncode == 0, res.stderr

    for cmd in [
        "littera doc add 'Document One'",
        "littera doc add 'Document Two'",
        "littera section add 1 'Introduction'",
        "littera section add 1 'Body'",
        "littera block add 1 'This is the first block' --lang en",
        "littera block add 1 'To jest drugi blok' --lang pl",
        "littera entity add concept 'Time'",
        "littera entity add person 'Aristotle'",
    ]:
        res = _run_cli(cmd, workdir)
        assert res.returncode == 0, f"{cmd} failed: {res.stderr}"

    # Start PG for the session duration
    littera_dir = workdir / ".littera"
    cfg = yaml.safe_load((littera_dir / "config.yml").read_text())
    manager = EmbeddedPostgresManager(littera_dir)
    manager.ensure()

    pg = cfg["postgres"]
    pg_cfg = PostgresConfig(
        data_dir=Path(pg["data_dir"]),
        port=pg["port"],
        db_name=pg["db_name"],
        initdb_path=str(manager.initdb_path()),
        pg_ctl_path=str(manager.pg_ctl_path()),
    )
    start_postgres(pg_cfg)

    try:
        yield workdir, cfg, pg_cfg
    finally:
        stop_postgres(pg_cfg)


@pytest.fixture
def tui_state(seeded_work):
    """Per-test: fresh AppState connected to seeded DB."""
    workdir, cfg, pg_cfg = seeded_work

    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)

    state = AppState()
    state.db = conn
    state.work = cfg

    try:
        yield state
    finally:
        conn.close()


@pytest.fixture
def seeded_ids(seeded_work):
    """Per-test: look up real UUIDs of seeded data."""
    _, cfg, pg_cfg = seeded_work

    conn = psycopg.connect(dbname=pg_cfg.db_name, port=pg_cfg.port)

    cur = conn.cursor()
    cur.execute("SELECT id, title FROM documents ORDER BY created_at")
    docs = cur.fetchall()

    cur.execute(
        "SELECT s.id, s.title FROM sections s "
        "JOIN documents d ON d.id = s.document_id "
        "ORDER BY d.created_at, s.order_index"
    )
    secs = cur.fetchall()

    cur.execute(
        "SELECT b.id, b.language, b.source_text FROM blocks b "
        "JOIN sections s ON s.id = b.section_id "
        "JOIN documents d ON d.id = s.document_id "
        "ORDER BY d.created_at, s.order_index, b.created_at"
    )
    blks = cur.fetchall()

    cur.execute(
        "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
    )
    ents = cur.fetchall()

    conn.close()

    return {
        "doc1_id": str(docs[0][0]),
        "doc1_title": docs[0][1],
        "doc2_id": str(docs[1][0]),
        "doc2_title": docs[1][1],
        "sec1_id": str(secs[0][0]),
        "sec1_title": secs[0][1],
        "sec2_id": str(secs[1][0]),
        "sec2_title": secs[1][1],
        "blk1_id": str(blks[0][0]),
        "blk2_id": str(blks[1][0]),
        "ent1_id": str(ents[0][0]),
        "ent2_id": str(ents[1][0]),
    }
